from vehicle_detector import VehicleDetector


def main():
    detector = VehicleDetector()

    vehicles = detector.detect("data/images/bus.jpg")

    print("\n===== CITY ANPR VEHICLE DETECTOR =====")

    if not vehicles:
        print("No vehicles detected.")

    for i, vehicle in enumerate(vehicles, start=1):
        print(
            f"Vehicle #{i} | "
            f"Type: {vehicle['class']} | "
            f"Confidence: {vehicle['confidence']:.2f} | "
            f"BBox: {vehicle['bbox']}"
        )

    print("=======================================\n")


if __name__ == "__main__":
    main()