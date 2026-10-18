TREE_SPECIES = [
    {
        "scientific_name": "Mimusops elengi",
        "common_name": "Bunga Tanjung",
        "size_class": "Medium",
        "canopy": "Compact to rounded",
        "notes": "Consider where a medium-sized "
                 "urban tree is appropriate."
    },
    {
        "scientific_name": "Lagerstroemia speciosa",
        "common_name": "Bungor",
        "size_class": "Medium",
        "canopy": "Rounded",
        "notes": "Consider for urban shade "
                 "and flowering landscape design."
    },
    {
        "scientific_name": "Hopea odorata",
        "common_name": "Merawan Siput Jantan",
        "size_class": "Large",
        "canopy": "Broad at maturity",
        "notes": "Consider only where sufficient "
                 "long-term growing space exists."
    }
]

# Produce species recommendation 
def recommend_tree_species(planting_assessment):

    if planting_assessment == "POTENTIAL_GROUND":
        return {
            "status": "CONDITIONAL_RECOMMENDATION",
            "species": TREE_SPECIES,
            "reason": (
                "Potential planting ground identified. "
                "Verify soil conditions, planting width, "
                "root space, drainage, utilities, "
                "ownership and canopy clearance "
                "before selecting a species."
            )
        }

    if planting_assessment == "ENGINEERING_ASSESSMENT":
        return {
            "status": "SITE_REDESIGN_REQUIRED",
            "species": [],
            "reason": (
                "Built-up land cover detected. "
                "Verify whether pavement modification "
                "or an engineered planting area "
                "is feasible before selecting a tree."
            )
        }

    if planting_assessment == "EXISTING_TREE_COVER":
        return {
            "status": "EXISTING_VEGETATION_REVIEW",
            "species": [],
            "reason": (
                "Existing tree cover detected. "
                "Inspect existing vegetation before "
                "considering additional planting."
            )
        }

    if planting_assessment == "EXCLUDED_LANDCOVER":
        return {
            "status": "NOT_RECOMMENDED",
            "species": [],
            "reason": (
                "Land-cover category excluded from "
                "ordinary urban tree-planting screening."
            )
        }

    return {
        "status": "INSUFFICIENT_SITE_DATA",
        "species": [],
        "reason": (
            "More land-cover and site information "
            "is required before recommending trees."
        )
    }
