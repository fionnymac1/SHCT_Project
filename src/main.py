import config
from simulation import *

def load_data(filepath):
    """
    Reads a text file containing comma-separated numerical values.
    Handles both single-line and multi-line formats.
    """
    data = []
    try:
        with open(filepath, 'r') as file:
            # Read the entire file content into one string
            content = file.read()
            
            # Replace any newline characters with commas to ensure 
            # multi-line files are processed smoothly
            content = content.replace('\n', ',')
            
            # Split the string into a list of individual strings at every comma
            raw_values = content.split(',')
            
            for val in raw_values:
                clean_val = val.strip() # Remove any stray spaces
                if clean_val:           # Ensure it is not empty (e.g., from a trailing comma)
                    data.append(float(clean_val))
                    
        return data
        
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return []
    except ValueError as e:
        print(f"Error converting data in {filepath} to float. Check for non-numeric characters. Details: {e}")
        return []

def main():
    print("--- Starting Server Room Cooling Simulation ---")
    
    # 1. Load Data
    print("Loading data files...")
    server_heat_data = load_data(config.FILE_SERVER_HEAT)
    
    # Check if data loaded successfully before proceeding
    if not server_heat_data:
        print("Failed to load server heat data. Exiting.")
        return

    # 2. Execute Task 1: Determine System Limits
    print("\n--- Executing Task 1 ---")
    max_flow_limit, peak_cooling_demand = determine_system_limits(server_heat_data)
    
    # 3. Output Results
    print(f"Maximum Volumetric Flow Limit: {max_flow_limit:.3f} m^3/s")
    print(f"Peak Cooling Demand (Required Power): {peak_cooling_demand:.2f} kW")


if __name__ == "__main__":
    main()