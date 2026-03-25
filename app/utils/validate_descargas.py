import datetime, argparse, os, json, re

from dotenv import load_dotenv
from app.helper.loggerV2 import LoggerV2

def validate_downloads(logger, date_str : str):
    """Function to process notifications and validate downloads for a given date (YYYY-MM-DD)."""
    try:
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        date_str_fmt = date_obj.strftime("%Y%m%d")
    except ValueError:
        logger.error("RobotDescargas", "Validate", "Failure", "Invalid date format. Please use YYYY-MM-DD.")
        return

    # Paths
    load_dotenv()
    network_path = os.getenv("NETWORK_PATH")
    download_dir = os.getenv("DOWNLOAD_DIR")
    json_path = os.path.join(
        network_path,
        "Documents", "workspace","redtrust-automation", "files",
        "descargas_debug_files",
        f"notifications_{date_str_fmt}.json"
    )
    # Carpeta base revisar\{date}\
    directory_path = os.path.join(download_dir, "revisar", f"{date_str_fmt}")
    validations_dir = os.path.join(network_path, "Documents", "workspace","redtrust-automation","files","validations")

    # Load JSON counts (adapted to new structure)
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        json_counts = {}
        for client_id, client_info in data.items():
            notificaciones = client_info.get('notificaciones', {})
            count = sum(len(lst) for lst in notificaciones.values())
            json_counts[client_id] = count
        logger.info("RobotDescargas", "Validate", "Pending", f"Loaded JSON file: {json_path}")
    except Exception as e:
        logger.error("RobotDescargas", "Validate", "Failure", f"Error loading JSON: {e}")
        json_counts = {}

    # Contar archivos por cliente en con-expediente y sin-expediente, ignorando la fecha
    file_counts = {}
    pattern = re.compile(r"CL (\d+) EXP")
    # Subcarpetas a revisar
    for subfolder in ["con-expediente", "sin-expediente"]:
        folder_path = os.path.join(directory_path, subfolder)
        if not os.path.isdir(folder_path):
            continue
        for filename in os.listdir(folder_path):
            match = pattern.search(filename)
            if match:
                client_id = match.group(1)
                file_counts[client_id] = file_counts.get(client_id, 0) + 1

    

    # Compare and prepare output
    all_client_ids = set(json_counts) | set(file_counts)
    output_lines = ["\nComparación de conteos por cliente:"]
    for client_id in sorted(all_client_ids, key=int):
        json_count = json_counts.get(client_id, 0)
        file_count = file_counts.get(client_id, 0)
        if json_count == file_count:
            status = "✅ Cuadra"
            logger.info("RobotDescargas", "Validate", "Pending", f"Cliente {client_id}: Cuadra (JSON: {json_count}, Archivos: {file_count})")
        else:
            status = f"❌ No cuadra (JSON: {json_count}, Archivos: {file_count})"
            logger.info("RobotDescargas", "Validate", "Pending", f"Cliente {client_id}: No cuadra (JSON: {json_count}, Archivos: {file_count})")
        output_lines.append(f"Cliente {client_id}: {status}")

    # Write results (with emojis)
    os.makedirs(validations_dir, exist_ok=True)
    output_path = os.path.join(validations_dir, f"check_downloads_{date_str_fmt}.txt")
    with open(output_path, "w", encoding="utf-8") as txt_file:
        for line in output_lines:
            txt_file.write(line + "\n")


def main():
    parser = argparse.ArgumentParser(description="Process notifications and validate downloads.")
    parser.add_argument("--date", help="Date in format YYYY-MM-DD (e.g., 2025-06-04)")
    args = parser.parse_args()

    if not args.date:
        args.date = input("Enter date (YYYY-MM-DD): ").strip()

    simple_logger = LoggerV2(
        execution_id=f"34567890065678900722137918",
        module="Descargas",
        class_name="ValidateDescargas",
        log_dir=r"logs\descargas",
        filename=f"descargas_{args.date.replace('-', '')}",
    )

    validate_downloads(simple_logger, args.date)

if __name__ == "__main__":
    main()