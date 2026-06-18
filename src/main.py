import config
from simulation import *
from visualization import *

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

    # Example execution to generate maps for your combinations
    refrigerants = config.REFRIGERANTS  
    bores = config.COMPRESSOR_BORES_MM

    # Generate one map to test
    test_map = generate_performance_map("Propane", 50)
    print(test_map)

if __name__ == "__main__":
    main()