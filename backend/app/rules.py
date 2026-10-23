from app.models import ItemType, Resource, Shelter


REQUIRED_RESOURCES: dict[ItemType, tuple[Resource, ...]] = {
    ItemType.COOKED_MEAL: (),
    ItemType.SHORT_LIFE_MEDICINE: (),
    ItemType.RAW_RATION_KIT: (Resource.COOKING_FUEL,),
    ItemType.INFANT_FORMULA: (Resource.CLEAN_WATER,),
}


def is_compatible(item_type: ItemType, shelter: Shelter) -> tuple[bool, str]:
    missing = [
        resource
        for resource in REQUIRED_RESOURCES[item_type]
        if resource not in shelter.resources
    ]
    if missing:
        return False, f"Missing required resource: {missing[0].value}"
    return True, ""
