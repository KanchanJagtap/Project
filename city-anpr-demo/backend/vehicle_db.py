VEHICLE_DATABASE = {
    "MH12AB1234": {
        "vehicle_type": "Car",
        "manufacturer": "Hyundai",
        "model": "i20",
        "fuel": "Petrol",
        "registration_state": "Maharashtra",
        "registration_status": "Active",
    },
    "MH14CD5678": {
        "vehicle_type": "SUV",
        "manufacturer": "Mahindra",
        "model": "XUV700",
        "fuel": "Diesel",
        "registration_state": "Maharashtra",
        "registration_status": "Active",
    },
    "MH15EF9012": {
        "vehicle_type": "Truck",
        "manufacturer": "Tata",
        "model": "LPT 709",
        "fuel": "Diesel",
        "registration_state": "Maharashtra",
        "registration_status": "Commercial",
    },
}


def get_vehicle_details(plate_number: str):
    return VEHICLE_DATABASE.get(plate_number)