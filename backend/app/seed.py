from app import clock
from app.models import (
    Donor,
    Location,
    Resource,
    Rider,
    RiderStatus,
    Shelter,
)


def seed_entities() -> tuple[dict[str, Donor], dict[str, Rider], dict[str, Shelter]]:
    donors = {
        "donor_1": Donor(
            id="donor_1",
            name="Grand Banquet Hall",
            location=Location(lat=18.5204, lng=73.8567),
        ),
        "donor_2": Donor(
            id="donor_2",
            name="Campus Hostel Mess",
            location=Location(lat=18.5260, lng=73.8500),
        ),
        "donor_3": Donor(
            id="donor_3",
            name="City Pharmacy",
            location=Location(lat=18.5150, lng=73.8620),
        ),
    }
    rider_data = (
        ("rider_1", "Aarav", 18.5300, 73.8500, 40),
        ("rider_2", "Diya", 18.5320, 73.8540, 40),
        ("rider_3", "Kabir", 18.5280, 73.8590, 60),
        ("rider_4", "Meera", 18.5350, 73.8620, 40),
        ("rider_5", "Ishaan", 18.5190, 73.8480, 60),
    )
    riders = {
        rider_id: Rider(
            id=rider_id,
            name=name,
            location=Location(lat=lat, lng=lng),
            capacity=capacity,
            status=RiderStatus.AVAILABLE,
            last_heartbeat_at=clock.now(),
            active_shipment_ids=[],
        )
        for rider_id, name, lat, lng, capacity in rider_data
    }
    shelters = {
        "shelter_a": Shelter(
            id="shelter_a",
            name="Shelter A",
            location=Location(lat=18.5400, lng=73.8700),
            demand_remaining=50,
            reserved_qty=0,
            is_open=True,
            resources=[Resource.CLEAN_WATER, Resource.COOKING_FUEL],
        ),
        "shelter_b": Shelter(
            id="shelter_b",
            name="Shelter B",
            location=Location(lat=18.5360, lng=73.8520),
            demand_remaining=80,
            reserved_qty=0,
            is_open=True,
            resources=[Resource.COOKING_FUEL],
        ),
        "shelter_c": Shelter(
            id="shelter_c",
            name="Shelter C",
            location=Location(lat=18.5120, lng=73.8580),
            demand_remaining=60,
            reserved_qty=0,
            is_open=True,
            resources=[Resource.CLEAN_WATER, Resource.COOKING_FUEL],
        ),
    }
    return donors, riders, shelters
