VEHICLE_DATABASE = {
    "MH12AB1234": {
        "vehicle_type": "Car",
        "manufacturer": "Hyundai",
        "model": "i20",
        "fuel": "Petrol",
        "registration_state": "Maharashtra",
        "registration_rto": "Pune",
        "registration_status": "Active",
        "vehicle_category": "Private",
        "demo_owner": "Demo Owner 01",
    },

    "MH14CD5678": {
        "vehicle_type": "SUV",
        "manufacturer": "Mahindra",
        "model": "XUV700",
        "fuel": "Diesel",
        "registration_state": "Maharashtra",
        "registration_rto": "Pimpri-Chinchwad",
        "registration_status": "Active",
        "vehicle_category": "Private",
        "demo_owner": "Demo Owner 02",
    },

    "MH15EF9012": {
        "vehicle_type": "Truck",
        "manufacturer": "Tata",
        "model": "LPT 709",
        "fuel": "Diesel",
        "registration_state": "Maharashtra",
        "registration_rto": "Nashik",
        "registration_status": "Active",
        "vehicle_category": "Commercial",
        "demo_owner": "Demo Operator 01",
    },

    "MH16GH3456": {
        "vehicle_type": "Motorcycle",
        "manufacturer": "Bajaj",
        "model": "Pulsar 150",
        "fuel": "Petrol",
        "registration_state": "Maharashtra",
        "registration_rto": "Ahilyanagar",
        "registration_status": "Active",
        "vehicle_category": "Private",
        "demo_owner": "Demo Owner 03",
    },

    "MH17JK7890": {
        "vehicle_type": "Car",
        "manufacturer": "Maruti Suzuki",
        "model": "Swift",
        "fuel": "Petrol",
        "registration_state": "Maharashtra",
        "registration_rto": "Shrirampur",
        "registration_status": "Active",
        "vehicle_category": "Private",
        "demo_owner": "Demo Owner 04",
    },

    "MH18LM2468": {
        "vehicle_type": "Bus",
        "manufacturer": "Tata",
        "model": "Starbus",
        "fuel": "Diesel",
        "registration_state": "Maharashtra",
        "registration_rto": "Dhule",
        "registration_status": "Active",
        "vehicle_category": "Commercial",
        "demo_owner": "Demo Operator 02",
    },
}


def get_vehicle_details(plate_number: str):
    return VEHICLE_DATABASE.get(plate_number.upper())


def vehicle_exists(plate_number: str):
    return plate_number.upper() in VEHICLE_DATABASE
