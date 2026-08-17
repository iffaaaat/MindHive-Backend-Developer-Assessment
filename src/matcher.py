from collections import defaultdict

from rapidfuzz import fuzz

from .data_loader import (
    load_catalogues,
    load_customer_sku_map,
)
from .normalizer import (
    normalize_text,
    extract_numbers,
)


def extract_variant(text):
    """
    Extract the most specific known product variant.

    For grinder-disc queries, "grinding disc" can describe
    the general product family, while "flap" or "cutting"
    identifies the actual catalogue variant.
    """

    tokens = set(
        normalize_text(text).split()
    )

    if "flap" in tokens:
        return "flap"

    if "cutting" in tokens:
        return "cutting"

    if "grinding" in tokens:
        return "grinding"

    return None

class Matcher:

    def __init__(self):
        self.catalogues = load_catalogues()
        self.aliases = load_customer_sku_map()

        self.active_catalogues = {}
        self.item_lookup = {}
        self.barcode_lookup = {}
        self.alias_lookup = defaultdict(list)

        self._build_indexes()


    def _build_indexes(self):
        """
        Prepare fast lookup structures for:
        - active catalogue items
        - item codes
        - barcodes
        - customer SKU aliases
        - normalized catalogue search text
        """

        for tenant, items in self.catalogues.items():

            # -----------------------------------
            # Keep only active catalogue items
            # -----------------------------------
            active_items = [
                item
                for item in items
                if item["disabled"] == "0"
            ]

            self.active_catalogues[tenant] = active_items


            # -----------------------------------
            # Build normalized search text
            # -----------------------------------
            for item in active_items:

                # Primary retrieval field.
                #
                # Experiments showed that matching against
                # item_name substantially outperformed matching
                # against concatenated catalogue text.
                item["_name_text"] = normalize_text(
                    item["item_name"]
                )

                # Keep a richer representation for later
                # attribute/reranking checks.
                item["_search_text"] = normalize_text(
                    " ".join(
                        [
                            item["item_name"],
                            item["description"],
                            item["brand"],
                        ]
                    )
                )


                # -----------------------------------
                # Item-code lookup
                # -----------------------------------
            self.item_lookup[tenant] = {
                item["item_code"]: item
                for item in active_items
            }


            # -----------------------------------
            # Barcode lookup
            # -----------------------------------
            barcode_index = defaultdict(list)

            for item in active_items:

                barcode = item["barcode"].strip()

                if barcode:
                    barcode_index[barcode].append(
                        item
                    )

            self.barcode_lookup[tenant] = (
                barcode_index
            )


        # -----------------------------------
        # Customer SKU alias lookup
        # -----------------------------------
        for alias in self.aliases:

            key = (
                alias["tenant"],
                alias["customer_id"],
                alias["customer_sku"],
            )

            self.alias_lookup[key].append(
                alias
            )


    def resolve_barcode(self, line):
        """
        Resolve a barcode only when it points to exactly
        one active item within the correct tenant.
        """

        tenant = line["tenant"]
        barcode = line["raw_barcode"].strip()

        if not barcode:
            return None

        matches = self.barcode_lookup[
            tenant
        ].get(
            barcode,
            [],
        )

        # Do not guess if barcode is ambiguous.
        if len(matches) != 1:
            return None

        return matches[0]


    def resolve_alias(self, line):
        """
        Resolve a customer's buyer SKU only when:
        - tenant matches
        - customer matches
        - mapping is valid on order date
        - mapping resolves to exactly one logical item

        If a valid alias points to a disabled "-OLD" item,
        attempt to resolve the corresponding active same-base
        successor.

        This behaviour is based on the supplied catalogue
        structure and was validated against the labelled data.
        """

        tenant = line["tenant"]
        customer_id = line["customer_id"]
        buyer_sku = line["buyer_sku"].strip()
        order_date = line["order_date"]

        if not buyer_sku:
            return None

        key = (
            tenant,
            customer_id,
            buyer_sku,
        )

        mappings = self.alias_lookup.get(
            key,
            [],
        )

        valid_targets = {}


        for alias in mappings:

            valid_from = (
                alias["valid_from"].strip()
            )

            valid_to = (
                alias["valid_to"].strip()
            )


            # -----------------------------------
            # Date validity
            # -----------------------------------

            if (
                valid_from
                and order_date < valid_from
            ):
                continue

            if (
                valid_to
                and order_date > valid_to
            ):
                continue


            target_code = alias["item_code"]


            # -----------------------------------
            # First try active target directly
            # -----------------------------------

            item = self.item_lookup[
                tenant
            ].get(
                target_code
            )

            if item:

                valid_targets[
                    item["item_code"]
                ] = item

                continue


            # -----------------------------------
            # Superseded "-OLD" target
            # -----------------------------------

            if target_code.endswith("-OLD"):

                successor_code = (
                    target_code[:-4]
                )

                successor = self.item_lookup[
                    tenant
                ].get(
                    successor_code
                )

                if successor:

                    valid_targets[
                        successor["item_code"]
                    ] = successor


        # -----------------------------------
        # Only trust a uniquely resolved target
        # -----------------------------------

        if len(valid_targets) != 1:
            return None

        return next(
            iter(valid_targets.values())
        )


    def retrieve_lexical_candidates(
        self,
        line,
        limit=20,
    ):
        """
        Retrieve candidate items using token-set
        similarity against the catalogue item name.

        Benchmarking on the labelled training set showed
        that token_set_ratio against item_name produced
        substantially higher top-K recall than WRatio
        against concatenated catalogue text.
        """

        tenant = line["tenant"]

        query = normalize_text(
            line["raw_text"]
        )

        if not query:
            return []

        candidates = []

        for item in self.active_catalogues[
            tenant
        ]:

            target = item["_name_text"]

            lexical_score = fuzz.token_set_ratio(
                query,
                target,
            )

            candidates.append(
                {
                    "item": item,
                    "lexical_score":
                        lexical_score / 100.0,
                }
            )

        candidates.sort(
            key=lambda candidate:
                candidate["lexical_score"],
            reverse=True,
        )

        return candidates[:limit]


    def score_candidate(
        self,
        line,
        candidate,
    ):
        """
        Add structured evidence to a retrieved candidate.

        rank_score:
            Used to order candidates.

        confidence_score:
            Represents evidence that is safer to use
            for AUTO/REVIEW decisions.

        Price is useful for reranking, but is not
        treated as direct confidence.
        """

        item = candidate["item"]

        query_text = normalize_text(
            line["raw_text"]
        )

        item_text = item["_search_text"]

        lexical_score = (
            candidate["lexical_score"]
        )


        # -----------------------------------
        # Brand agreement
        # -----------------------------------

        brand = normalize_text(
            item["brand"]
        )

        brand_match = (
            1.0
            if brand and brand in query_text
            else 0.0
        )


        # -----------------------------------
        # Numeric agreement
        # -----------------------------------

        query_numbers = set(
            extract_numbers(
                query_text
            )
        )

        item_numbers = set(
            extract_numbers(
                item_text
            )
        )

        if query_numbers:

            shared_numbers = (
                query_numbers
                & item_numbers
            )

            numeric_score = (
                len(shared_numbers)
                / len(query_numbers)
            )

        else:

            numeric_score = 0.5


        # -----------------------------------
        # Variant / grade agreement
        # -----------------------------------

        query_variant = extract_variant(
            query_text
        )

        item_variant = extract_variant(
            item["item_name"]
        )

        if query_variant:

            if item_variant == query_variant:
                variant_score = 1.0
            else:
                variant_score = 0.0

        else:
            variant_score = 0.5


        # -----------------------------------
        # Price consistency
        # -----------------------------------

        price_score = 0.5

        raw_order_price = (
            line["unit_price"].strip()
        )

        raw_catalogue_price = (
            item["list_price"].strip()
        )

        if (
            raw_order_price
            and raw_catalogue_price
        ):

            try:

                order_price = float(
                    raw_order_price
                )

                catalogue_price = float(
                    raw_catalogue_price
                )

                if (
                    order_price > 0
                    and catalogue_price > 0
                ):

                    relative_difference = abs(
                        order_price
                        - catalogue_price
                    ) / catalogue_price

                    if relative_difference <= 0.10:
                        price_score = 1.0

                    elif relative_difference <= 0.25:
                        price_score = 0.8

                    elif relative_difference <= 0.50:
                        price_score = 0.5

                    else:
                        price_score = 0.0

            except ValueError:
                pass


        # -----------------------------------
        # Ranking score
        #
        # Price participates here because our
        # experiment showed that it improves
        # candidate ordering.
        # -----------------------------------

        rank_score = (
            0.55 * lexical_score
            + 0.10 * brand_match
            + 0.15 * numeric_score
            + 0.10 * variant_score
            + 0.10 * price_score
        )


        # -----------------------------------
        # Confidence evidence
        #
        # Price is intentionally excluded.
        #
        # We want price to help pick between plausible
        # candidates without making the system falsely
        # believe that the match is intrinsically safer.
        # -----------------------------------

        confidence_score = (
            0.65 * lexical_score
            + 0.10 * brand_match
            + 0.15 * numeric_score
        )


        return {
            **candidate,
            "brand_match": brand_match,
            "numeric_score": numeric_score,
            "price_score": price_score,
            "variant_score": variant_score,
            "rank_score": rank_score,
            "confidence_score": confidence_score,

            # Keep "score" temporarily for compatibility
            # with existing evaluation scripts.
            "score": rank_score,
        }

    def rank_candidates(
        self,
        line,
        limit=5,
        retrieval_limit=20,
    ):
        """
        Retrieve a wider lexical shortlist first,
        then rerank it using structured evidence.

        The wider shortlist helps avoid losing the
        correct item before reranking.
        """

        candidates = (
            self.retrieve_lexical_candidates(
                line,
                limit=retrieval_limit,
            )
        )

        scored = [
            self.score_candidate(
                line,
                candidate,
            )
            for candidate in candidates
        ]

        scored.sort(
            key=lambda candidate:
                candidate["rank_score"],
            reverse=True,
        )

        return scored[:limit]


    def decide(
    self,
    line,
    auto_score_threshold=0.85,
    auto_margin_threshold=0.10,
    no_match_threshold=0.70,
    ):
        """
        Produce a three-way matching decision:

        AUTO:
            Evidence is strong enough to accept automatically.

        REVIEW:
            One or more plausible candidates exist, but the
            evidence is not strong enough for automatic action.

        NO_MATCH:
            Candidate evidence is too weak to justify a
            catalogue recommendation.

        Strong identifier evidence is evaluated before
        lexical retrieval.
        """

        # --------------------------------------------------
        # 1. Strong identifier lane
        # --------------------------------------------------

        barcode_match = self.resolve_barcode(line)
        alias_match = self.resolve_alias(line)


        # Both strong signals exist and agree.
        if barcode_match and alias_match:

            if (
                barcode_match["item_code"]
                == alias_match["item_code"]
            ):

                return {
                    "item_code": barcode_match["item_code"],
                    "confidence": 1.0,
                    "decision": "auto",
                    "reason": (
                        "unique active barcode and validated "
                        "customer alias agree"
                    ),
                    "source": "barcode+alias",
                    "margin": None,
                    "candidates": [],
                }


            # Contradictory strong identifiers are unsafe.
            return {
                "item_code": None,
                "confidence": 0.0,
                "decision": "review",
                "reason": (
                    "barcode and customer alias resolve "
                    "to different active items"
                ),
                "source": "identifier_conflict",
                "margin": None,
                "candidates": [],
            }


        # Unique barcode.
        if barcode_match:

            return {
                "item_code": barcode_match["item_code"],
                "confidence": 1.0,
                "decision": "auto",
                "reason": "unique active barcode match",
                "source": "barcode",
                "margin": None,
                "candidates": [],
            }


        # Valid alias, including validated -OLD successor.
        if alias_match:

            return {
                "item_code": alias_match["item_code"],
                "confidence": 1.0,
                "decision": "auto",
                "reason": (
                    "validated unique customer SKU alias"
                ),
                "source": "alias",
                "margin": None,
                "candidates": [],
            }


        # --------------------------------------------------
        # 2. Lexical / structured candidate ranking
        # --------------------------------------------------

        candidates = self.rank_candidates(
            line,
            limit=20,
            retrieval_limit=30,
        )


        if not candidates:

            return {
                "item_code": None,
                "confidence": 0.0,
                "decision": "no_match",
                "reason": "no catalogue candidates retrieved",
                "source": "lexical",
                "margin": 0.0,
                "candidates": [],
            }


        chosen = candidates[0]

        confidence = (
            chosen["confidence_score"]
        )


        # --------------------------------------------------
        # Find the strongest competing candidate based on
        # confidence evidence, not rank_score.
        # --------------------------------------------------

        if len(candidates) >= 2:

            strongest_competitor_confidence = max(
                candidate["confidence_score"]
                for candidate in candidates[1:]
            )

            margin = (
                confidence
                - strongest_competitor_confidence
            )

        else:

            margin = confidence


        item_code = (
            chosen["item"]["item_code"]
        )


        # --------------------------------------------------
        # 3. AUTO region
        # --------------------------------------------------

        if (
            confidence >= auto_score_threshold
            and margin >= auto_margin_threshold
        ):

            return {
                "item_code": item_code,
                "confidence": confidence,
                "decision": "auto",
                "reason": (
                    "high candidate confidence with "
                    "clear separation from alternatives"
                ),
                "source": "lexical",
                "margin": margin,
                "candidates": candidates[:5],
            }


        # --------------------------------------------------
        # 4. NO_MATCH region
        # --------------------------------------------------

        if confidence < no_match_threshold:

            return {
                "item_code": None,
                "confidence": confidence,
                "decision": "no_match",
                "reason": (
                    "best catalogue candidate has "
                    "insufficient evidence"
                ),
                "source": "lexical",
                "margin": margin,
                "candidates": candidates[:5],
            }


        # --------------------------------------------------
        # 5. REVIEW region
        # --------------------------------------------------

        return {
            "item_code": item_code,
            "confidence": confidence,
            "decision": "review",
            "reason": (
                "plausible candidate found but confidence "
                "or candidate separation is insufficient "
                "for automatic matching"
            ),
            "source": "lexical",
            "margin": margin,
            "candidates": candidates[:5],
        }
