import csv
import os
import re
import shutil

csv_path = "evaluation/RQ1/dataset.csv"
output_dir = "evaluation/RQ1/target_contracts"
web3bugs_repo = "C:/Users/isjeon/Web3Bugs/contracts"

os.makedirs(output_dir, exist_ok=True)

rows = []
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)


def find_contract_in_dir(directory, target_contract, recursive=False):
    """Search for a .sol file containing 'contract X' or 'library X'."""
    pattern = re.compile(
        r'\b(?:contract|library|abstract\s+contract)\s+' + re.escape(target_contract) + r'\b'
    )
    if recursive:
        for root, dirs, files in os.walk(directory):
            for fname in files:
                if not fname.endswith(".sol"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as sf:
                        if pattern.search(sf.read()):
                            return fpath
                except Exception:
                    continue
    else:
        for fname in os.listdir(directory):
            if not fname.endswith(".sol"):
                continue
            fpath = os.path.join(directory, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as sf:
                    if pattern.search(sf.read()):
                        return fpath
            except Exception:
                continue
    return None


copied = []
not_found = []

for row in rows:
    entry_id = row["id"]
    source = row["source"]
    contract_name = row["contract"]
    source_file = row["source_file"]

    if source == "numscout":
        if os.path.isfile(source_file):
            ext = os.path.splitext(source_file)[1]
            dest = os.path.join(output_dir, f"{entry_id}{ext}")
            shutil.copy2(source_file, dest)
            copied.append((entry_id, source_file, dest))
        else:
            not_found.append((entry_id, source_file, "source_file not found"))
        continue

    # For entries with multiple contracts (e.g., "mint;burn"), use the first
    target_contract = contract_name.split(";")[0] if ";" in contract_name else contract_name

    # Step 1: Search in dataset directory (flat .sol files)
    found_file = None
    if os.path.isdir(source_file):
        found_file = find_contract_in_dir(source_file, target_contract, recursive=False)

    # Step 2: If not found, search original Web3Bugs repo recursively
    if not found_file:
        # Extract contest ID from entry_id: web3bugs_{contest}_{severity}_{num}
        parts = entry_id.split("_")
        contest_id = parts[1]  # e.g., "35" from "web3bugs_35_H_12"
        repo_dir = os.path.join(web3bugs_repo, contest_id)
        if os.path.isdir(repo_dir):
            found_file = find_contract_in_dir(repo_dir, target_contract, recursive=True)

    if found_file:
        dest = os.path.join(output_dir, f"{entry_id}.sol")
        shutil.copy2(found_file, dest)
        copied.append((entry_id, found_file, dest))
    else:
        not_found.append((entry_id, source_file, f"'{target_contract}' not found"))

print(f"Copied: {len(copied)}")
for entry_id, src, dst in copied:
    # Shorten source path for display
    short_src = src.replace("C:/Users/isjeon/Web3Bugs/contracts/", "Web3Bugs/")
    short_src = short_src.replace("Dataset/Web3Bugs/", "Dataset/")
    print(f"  {entry_id}: {os.path.basename(src)}")

if not_found:
    print(f"\nNot found: {len(not_found)}")
    for entry_id, path, reason in not_found:
        print(f"  {entry_id}: {reason}")
