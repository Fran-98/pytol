import pprint

def _parse_value(val_str):
    """Helper function to convert a string value to an appropriate type."""
    val_str = val_str.strip()
    
    # Handle empty values
    if not val_str:
        return ""
        
    # Boolean
    if val_str.lower() == 'true':
        return True
    if val_str.lower() == 'false':
        return False
        
    # Vector/Tuple like (x, y, z)
    if val_str.startswith('(') and val_str.endswith(')'):
        try:
            # Remove parentheses and split by comma, then convert each part to float
            return tuple(float(x) for x in val_str[1:-1].split(','))
        except (ValueError, TypeError):
            return val_str # Return as string if conversion fails
            
    # List separated by semicolons
    if ';' in val_str:
        # Return a list of non-empty items
        return [item for item in val_str.split(';') if item]

    # Number (float or int)
    try:
        # Check for scientific notation or decimal to decide float vs int
        if '.' in val_str or 'e' in val_str.lower():
            return float(val_str)
        return int(val_str)
    except ValueError:
        # If all else fails, it's a string
        return val_str

def _parse_block(lines_iterator):
    """Recursively parses a block of text enclosed in curly braces."""
    data_dict = {}
    
    for line in lines_iterator:
        line = line.strip()
        
        if not line:
            continue
        
        # End of the current block
        if line == '}':
            return data_dict
            
        # Key-value pair
        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            data_dict[key] = _parse_value(value)
        # A new block is starting
        else:
            key = line.strip()
            # The next line should be '{', so we skip it.
            try:
                if next(lines_iterator).strip() != '{':
                    # Handle cases where a block might be empty or formatted differently
                    continue 
            except StopIteration:
                break

            block_content = _parse_block(lines_iterator)
            
            # If a key (like 'Segment' or 'Chunk') appears multiple times, store as a list
            if key in data_dict:
                if not isinstance(data_dict[key], list):
                    data_dict[key] = [data_dict[key]] # Convert existing item to a list
                data_dict[key].append(block_content)
            else:
                data_dict[key] = block_content
                
    return data_dict

def parse_vtol_data(file_content):
    """
    Parses the full text of a VTOL VR map (.vtm) or mission (.vts) file.
    
    Args:
        file_content (str): The string content of the file.
        
    Returns:
        dict: A nested dictionary representing the file's structure.
    """
    lines = iter(file_content.strip().split('\n'))
    
    # The first line is the root object name (e.g., 'VTMapCustom')
    root_key = next(lines).strip()
    
    # The second line is the opening brace '{'
    next(lines)
    
    # Start parsing the main block
    return {root_key: _parse_block(lines)}

if __name__ == '__main__':
    file_path = "test_map/hMap2/hMap2.vtm"

    try:
        with open(file_path, "r") as f:
            vtm_content = f.read()

        print(f"Successfully read '{file_path}'. Parsing now...")
        
        # Call the parser function
        parsed_map_data = parse_vtol_data(vtm_content)
        
        print("\n--- Parse Complete! ---")
        
        # Example: Accessing specific data from the parsed map
        map_id = parsed_map_data.get("VTMapCustom", {}).get("mapID")
        max_height = parsed_map_data.get("VTMapCustom", {}).get("TerrainSettings", {}).get("maxMtnHeight")
        
        print(f"Map ID: {map_id}")
        print(f"Max Mountain Height: {max_height} meters")

        # Using pprint to cleanly print a small, complex section (like the first prefab)
        first_prefab = parsed_map_data.get("VTMapCustom", {}).get("StaticPrefabs", {}).get("StaticPrefab", [{}])[0]
        print("\n--- Data for the first StaticPrefab: ---")
        pprint.pprint(first_prefab)

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except Exception as e:
        print(f"An error occurred during parsing: {e}")