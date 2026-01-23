"""
Solidity Contract Extractor
- Extracts target contract, state variables, structs, events, modifiers, and target functions
- Based on vulnerability line numbers from NumScout JSON files
"""

import os
import re
import json
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass


@dataclass
class CodeBlock:
    """Represents a code block with start/end lines"""
    name: str
    start_line: int
    end_line: int
    block_type: str  # 'contract', 'function', 'struct', 'event', 'modifier', 'using', 'state_var'


def find_matching_brace(lines: List[str], start_line: int) -> int:
    """Find the line number where the opening brace is closed"""
    brace_count = 0
    started = False

    for i in range(start_line, len(lines)):
        line = lines[i]
        for char in line:
            if char == '{':
                brace_count += 1
                started = True
            elif char == '}':
                brace_count -= 1
                if started and brace_count == 0:
                    return i
    return len(lines) - 1


def parse_solidity_structure(lines: List[str]) -> Dict[str, List[CodeBlock]]:
    """Parse Solidity file to identify contracts, functions, structs, events, modifiers"""

    structure = {
        'contracts': [],
        'functions': [],
        'structs': [],
        'events': [],
        'modifiers': [],
        'usings': [],
        'state_vars': []
    }

    # Patterns
    contract_pattern = re.compile(r'^\s*(abstract\s+)?(contract|interface|library)\s+(\w+)(?:\s+is\s+[^{]+)?\s*\{?')
    function_pattern = re.compile(r'^\s*function\s+(\w+)\s*\(')
    struct_pattern = re.compile(r'^\s*struct\s+(\w+)\s*\{?')
    event_pattern = re.compile(r'^\s*event\s+(\w+)\s*\(')
    modifier_pattern = re.compile(r'^\s*modifier\s+(\w+)\s*(?:\([^)]*\))?\s*\{?')
    using_pattern = re.compile(r'^\s*using\s+(\w+)\s+for\s+[^;]+;')
    constructor_pattern = re.compile(r'^\s*constructor\s*\(')

    # State variable patterns (simplified)
    state_var_pattern = re.compile(r'^\s*(mapping|address|uint\d*|int\d*|bool|bytes\d*|string|enum)\s*[\[\(]?')
    visibility_pattern = re.compile(r'\b(public|private|internal|external|constant|immutable)\b')

    current_contract: Optional[CodeBlock] = None
    in_function_or_modifier = False

    for i, line in enumerate(lines):
        line_num = i + 1  # 1-indexed

        # Contract detection
        match = contract_pattern.match(line)
        if match:
            contract_name = match.group(3)
            end_line = find_matching_brace(lines, i)
            current_contract = CodeBlock(contract_name, line_num, end_line + 1, 'contract')
            structure['contracts'].append(current_contract)
            in_function_or_modifier = False
            continue

        # Skip if not inside a contract
        if current_contract is None:
            continue
        if line_num < current_contract.start_line or line_num > current_contract.end_line:
            current_contract = None
            continue

        # Function detection
        match = function_pattern.match(line)
        if match:
            func_name = match.group(1)
            end_line = find_matching_brace(lines, i)
            structure['functions'].append(CodeBlock(func_name, line_num, end_line + 1, 'function'))
            in_function_or_modifier = True
            continue

        # Constructor detection
        if constructor_pattern.match(line):
            end_line = find_matching_brace(lines, i)
            structure['functions'].append(CodeBlock('constructor', line_num, end_line + 1, 'function'))
            in_function_or_modifier = True
            continue

        # Fallback function detection (Solidity 0.4 style: function () payable { })
        fallback_pattern = re.compile(r'^\s*function\s*\(\s*\)')
        if fallback_pattern.match(line):
            end_line = find_matching_brace(lines, i)
            structure['functions'].append(CodeBlock('fallback', line_num, end_line + 1, 'function'))
            in_function_or_modifier = True
            continue

        # Receive/Fallback function detection (Solidity 0.6+ style)
        receive_pattern = re.compile(r'^\s*(receive|fallback)\s*\(\s*\)')
        if receive_pattern.match(line):
            func_name = receive_pattern.match(line).group(1)
            end_line = find_matching_brace(lines, i)
            structure['functions'].append(CodeBlock(func_name, line_num, end_line + 1, 'function'))
            in_function_or_modifier = True
            continue

        # Struct detection
        match = struct_pattern.match(line)
        if match:
            struct_name = match.group(1)
            end_line = find_matching_brace(lines, i)
            structure['structs'].append(CodeBlock(struct_name, line_num, end_line + 1, 'struct'))
            continue

        # Event detection
        match = event_pattern.match(line)
        if match:
            event_name = match.group(1)
            # Events can span multiple lines, find the closing )
            end_line = i
            paren_count = line.count('(') - line.count(')')
            while paren_count > 0 and end_line < len(lines) - 1:
                end_line += 1
                paren_count += lines[end_line].count('(') - lines[end_line].count(')')
            structure['events'].append(CodeBlock(event_name, line_num, end_line + 1, 'event'))
            continue

        # Modifier detection
        match = modifier_pattern.match(line)
        if match:
            modifier_name = match.group(1)
            end_line = find_matching_brace(lines, i)
            structure['modifiers'].append(CodeBlock(modifier_name, line_num, end_line + 1, 'modifier'))
            in_function_or_modifier = True
            continue

        # Using detection
        match = using_pattern.match(line)
        if match:
            using_name = match.group(1)
            structure['usings'].append(CodeBlock(using_name, line_num, line_num, 'using'))
            continue

        # Check if we're past all functions/modifiers (for state variable detection)
        # State variables are between contract start and first function/modifier/constructor
        if not in_function_or_modifier:
            # Check if this line is a state variable
            stripped = line.strip()
            if stripped and not stripped.startswith('//') and not stripped.startswith('/*'):
                if state_var_pattern.match(stripped) or visibility_pattern.search(stripped):
                    if ';' in line:  # Simple single-line state var
                        structure['state_vars'].append(CodeBlock('state_var', line_num, line_num, 'state_var'))

    return structure


def extract_vulnerability_lines(json_data: dict) -> Set[int]:
    """Extract all vulnerability line numbers from NumScout JSON"""
    lines = set()

    analysis = json_data.get('analysis', {})

    # Pattern to extract line number: "filename:LINE:col: Warning..."
    line_pattern = re.compile(r'[^:]+:(\d+):\d+:')

    for vuln_type, vuln_list in analysis.items():
        if isinstance(vuln_list, list):
            for item in vuln_list:
                if isinstance(item, list):
                    for warning in item:
                        match = line_pattern.match(warning)
                        if match:
                            lines.add(int(match.group(1)))
                elif isinstance(item, str):
                    match = line_pattern.match(item)
                    if match:
                        lines.add(int(match.group(1)))

    return lines


def find_target_functions(vuln_lines: Set[int], functions: List[CodeBlock]) -> List[CodeBlock]:
    """Find functions that contain vulnerability lines"""
    target_functions = []
    seen_names = set()

    for func in functions:
        for line in vuln_lines:
            if func.start_line <= line <= func.end_line:
                if func.name not in seen_names:
                    target_functions.append(func)
                    seen_names.add(func.name)
                break

    return target_functions


def find_target_contract(target_functions: List[CodeBlock], contracts: List[CodeBlock]) -> Optional[CodeBlock]:
    """Find the contract that contains target functions"""
    if not target_functions:
        return None

    func = target_functions[0]
    for contract in contracts:
        if contract.start_line <= func.start_line <= contract.end_line:
            return contract
    return None


def get_used_modifiers(lines: List[str], target_functions: List[CodeBlock]) -> Set[str]:
    """Extract modifier names used in target functions"""
    used_modifiers = set()

    # Common Solidity modifiers/keywords to exclude
    keywords = {'public', 'private', 'internal', 'external', 'view', 'pure', 'payable',
                'virtual', 'override', 'returns', 'memory', 'storage', 'calldata',
                'uint256', 'uint', 'int256', 'int', 'bool', 'address', 'bytes', 'string',
                'uint8', 'uint16', 'uint32', 'uint64', 'uint128', 'bytes32', 'bytes4'}

    for func in target_functions:
        func_line = lines[func.start_line - 1]
        # Extract words between ) and {
        match = re.search(r'\)\s*([^{]+)\s*\{', func_line)
        if match:
            modifiers_part = match.group(1)
            # Remove returns(...) part
            modifiers_part = re.sub(r'returns\s*\([^)]*\)', '', modifiers_part)
            # Split by spaces and filter
            words = re.findall(r'\b([a-zA-Z_]\w*)\b', modifiers_part)
            for word in words:
                if word.lower() not in {k.lower() for k in keywords}:
                    used_modifiers.add(word)

    return used_modifiers


def extract_contract(sol_path: str, json_path: str, output_path: str) -> bool:
    """Main extraction function"""

    # Read files
    with open(sol_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')

    with open(json_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    # Parse structure
    structure = parse_solidity_structure(lines)

    # Get vulnerability lines
    vuln_lines = extract_vulnerability_lines(json_data)
    if not vuln_lines:
        print(f"  No vulnerability lines found in JSON")
        return False

    print(f"  Vulnerability lines: {sorted(vuln_lines)}")

    # Find target functions
    target_functions = find_target_functions(vuln_lines, structure['functions'])
    if not target_functions:
        print(f"  No target functions found")
        return False

    print(f"  Target functions: {[f.name for f in target_functions]}")

    # Find target contract
    target_contract = find_target_contract(target_functions, structure['contracts'])
    if not target_contract:
        print(f"  No target contract found")
        return False

    print(f"  Target contract: {target_contract.name}")

    # Get used modifiers
    used_modifiers = get_used_modifiers(lines, target_functions)
    print(f"  Used modifiers: {used_modifiers}")

    # Filter elements within target contract
    contract_structs = [s for s in structure['structs']
                       if target_contract.start_line <= s.start_line <= target_contract.end_line]
    contract_events = [e for e in structure['events']
                      if target_contract.start_line <= e.start_line <= target_contract.end_line]
    contract_modifiers = [m for m in structure['modifiers']
                         if target_contract.start_line <= m.start_line <= target_contract.end_line]
    contract_usings = [u for u in structure['usings']
                      if target_contract.start_line <= u.start_line <= target_contract.end_line]

    # Collect all block ranges (functions, structs, events, modifiers) to exclude from state vars
    excluded_ranges = []
    for f in structure['functions']:
        if target_contract.start_line < f.start_line <= target_contract.end_line:
            excluded_ranges.append((f.start_line, f.end_line))
    for s in contract_structs:
        excluded_ranges.append((s.start_line, s.end_line))
    for e in contract_events:
        excluded_ranges.append((e.start_line, e.end_line))
    for m in contract_modifiers:
        excluded_ranges.append((m.start_line, m.end_line))
    for u in contract_usings:
        excluded_ranges.append((u.start_line, u.end_line))

    # Build output
    output_lines = []

    # 1. Contract declaration (first line only)
    output_lines.append(lines[target_contract.start_line - 1])

    # 2. Using statements
    for using in contract_usings:
        output_lines.append(lines[using.start_line - 1])

    if contract_usings:
        output_lines.append('')

    # 3. Structs
    for struct in contract_structs:
        for i in range(struct.start_line - 1, struct.end_line):
            output_lines.append(lines[i])
        output_lines.append('')

    # 4. Events
    for event in contract_events:
        for i in range(event.start_line - 1, event.end_line):
            output_lines.append(lines[i])
        output_lines.append('')

    # 5. State variables (all lines in contract not in any block)
    state_var_lines = []
    for i in range(target_contract.start_line, target_contract.end_line - 1):
        line = lines[i]
        line_num = i + 1

        # Skip if it's part of any excluded range
        skip = False
        for start, end in excluded_ranges:
            if start <= line_num <= end:
                skip = True
                break

        if not skip and line.strip() and not line.strip().startswith('//') and not line.strip().startswith('/*') and not line.strip().startswith('*'):
            state_var_lines.append(line)

    output_lines.extend(state_var_lines)
    if state_var_lines:
        output_lines.append('')

    # 6. Modifiers (if used and present in contract)
    available_modifier_names = {m.name for m in contract_modifiers}
    missing_modifiers = used_modifiers - available_modifier_names

    for modifier in contract_modifiers:
        if modifier.name in used_modifiers:
            for i in range(modifier.start_line - 1, modifier.end_line):
                output_lines.append(lines[i])
            output_lines.append('')

    # Add comments for missing modifiers
    if missing_modifiers:
        output_lines.append(f'    // Note: The following modifiers are not defined in this contract: {", ".join(sorted(missing_modifiers))}')
        output_lines.append('')

    # 7. Target functions
    for func in target_functions:
        for i in range(func.start_line - 1, func.end_line):
            output_lines.append(lines[i])
        output_lines.append('')

    # 8. Closing brace
    output_lines.append('}')

    # Write output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    print(f"  Output written to: {output_path}")
    return True


def process_all_targets(base_dir: str, output_base_dir: str):
    """Process all target folders"""
    target_dir = os.path.join(base_dir, 'Original', 'Target')

    if not os.path.exists(target_dir):
        print(f"Target directory not found: {target_dir}")
        return

    for vuln_type in os.listdir(target_dir):
        vuln_path = os.path.join(target_dir, vuln_type)
        if not os.path.isdir(vuln_path):
            continue

        print(f"\n{'='*60}")
        print(f"Processing: {vuln_type}")
        print('='*60)

        # Find .sol and .json pairs
        files = os.listdir(vuln_path)
        sol_files = [f for f in files if f.endswith('.sol')]

        for sol_file in sol_files:
            print(f"\n{sol_file}:")
            sol_path = os.path.join(vuln_path, sol_file)

            # Find corresponding JSON (with special unicode colon character)
            json_file = None
            for f in files:
                if f.startswith(sol_file) and f.endswith('.json'):
                    json_file = f
                    break

            if not json_file:
                print(f"  No JSON file found")
                continue

            json_path = os.path.join(vuln_path, json_file)

            # Extract contract name from JSON filename
            # Format: solfile.sol:ContractName.json or solfile.sol{unicode}ContractName.json
            contract_name = json_file.replace(sol_file, '').replace('.json', '')
            # Remove unicode colon character
            contract_name = contract_name.replace('\uf03a', '').replace(':', '')

            if not contract_name:
                # Fallback: extract from sol filename
                contract_name = sol_file.split('_')[-1].replace('.sol', '')

            output_path = os.path.join(output_base_dir, vuln_type, f"{contract_name}_contraction.sol")

            try:
                extract_contract(sol_path, json_path, output_path)
            except Exception as e:
                print(f"  Error: {e}")


if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_base_dir = os.path.join(base_dir, 'Contraction')

    process_all_targets(base_dir, output_base_dir)
    print("\n" + "="*60)
    print("Done!")
