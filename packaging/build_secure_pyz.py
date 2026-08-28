#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FT Data Cleaner - Secure PYZ build script
Purpose: create a publishable archive without sensitive information
Author: cc
Created: 2025-01-20
"""

import zipapp
import os
import shutil
import glob
import fnmatch
from pathlib import Path

VERSION = '2.18.0'

# --- Configuration ---
# Project root
source_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Output PYZ path
target_file = os.path.join(os.path.dirname(__file__), 'release', 'ft_data_cleaner.pyz')
# Application entry point
main_entry_point = 'gui.main_window:main'
# Top-level packages included in the PYZ
packages_to_include = ['gui', 'factories', 'shared', 'frontend']
# Root-level Python files included in the PYZ
files_to_include = []

# Security exclusions
EXCLUDE_PATTERNS = [
    '*.md',           # Markdown documents
    '*.MD',           # Uppercase Markdown documents
    '*.log',          # Log files
    '*.txt',          # Text files except requirements.txt
    'README*',        # README files
    '*_plan.md',      # Planning documents
    '*-plan.md',      # Planning documents
    'todo_*.md',      # TODO documents
    'project-status.md',
    'PERFORMANCE_OPTIMIZATION_REPORT.md',
    '__pycache__',    # Python cache directories
    '*.pyc',          # Compiled Python files
    '*.pyo',          # Optimized Python files
    '.git*',          # Git metadata
    'test_*',         # Test files
    '*_test.py',      # Test files
    '*.bat',          # Batch scripts
    'sample/',        # Sample data
    'ASEData/',       # Test data
    'output/',        # Generated output
    'packaging/',     # Packaging directory itself
]

def should_exclude_file(file_path):
    """Return whether a source file must be excluded from the archive."""
    file_name = os.path.basename(file_path)
    rel_path = os.path.relpath(file_path, source_root).replace(os.sep, '/')
    
    # Keep requirements.txt.
    if file_name == 'requirements.txt':
        return False
    
    # Apply exclusion patterns.
    for pattern in EXCLUDE_PATTERNS:
        if pattern.endswith('/') and pattern.rstrip('/') in rel_path.split('/'):
            return True
        if '*' in pattern:
            if fnmatch.fnmatch(file_name, pattern) or fnmatch.fnmatch(rel_path, pattern):
                return True
        elif pattern in file_name or pattern in rel_path:
            return True
    
    return False

def copy_directory_filtered(src, dst):
    """Copy a directory while filtering excluded files."""
    if not os.path.exists(dst):
        os.makedirs(dst)
    
    excluded_count = 0
    included_count = 0
    
    for root, dirs, files in os.walk(src):
        # Filter directories before descending.
        dirs[:] = [d for d in dirs if not should_exclude_file(os.path.join(root, d))]
        
        for file in files:
            src_file = os.path.join(root, file)
            
            if should_exclude_file(src_file):
                excluded_count += 1
                print(f"  [EXCLUDED] {os.path.relpath(src_file, src)}")
                continue
            
            # Calculate destination path.
            rel_path = os.path.relpath(src_file, src)
            dst_file = os.path.join(dst, rel_path)
            
            # Ensure the destination directory exists.
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
            
            # Copy the file.
            shutil.copy2(src_file, dst_file)
            included_count += 1
    
    return included_count, excluded_count

def create_secure_archive():
    """Create ft_data_cleaner.pyz without excluded or sensitive content."""
    
    # Temporary build source directory.
    temp_source_dir = os.path.join(os.path.dirname(__file__), '_temp_secure_build_src')
    
    # Ensure the release directory exists.
    release_dir = os.path.dirname(target_file)
    os.makedirs(release_dir, exist_ok=True)

    # Remove stale build state and the previous archive.
    if os.path.exists(temp_source_dir):
        shutil.rmtree(temp_source_dir)
    if os.path.exists(target_file):
        os.remove(target_file)
        print(f"Removed previous {os.path.basename(target_file)}")

    os.makedirs(temp_source_dir, exist_ok=True)
    print(f"Created temporary directory: {temp_source_dir}")

    total_included = 0
    total_excluded = 0

    # Copy required packages with filtering.
    for package_name in packages_to_include:
        src_path = os.path.join(source_root, package_name)
        if os.path.isdir(src_path):
            dest_path = os.path.join(temp_source_dir, package_name)
            print(f"Filtering and copying {package_name}...")
            included, excluded = copy_directory_filtered(src_path, dest_path)
            total_included += included
            total_excluded += excluded
            print(f"  [DONE] {package_name}: included {included}, excluded {excluded}")
        else:
            print(f"WARNING: package directory not found, skipping: {package_name}")
            
    # Copy required root-level Python files.
    for file_name in files_to_include:
        src_path = os.path.join(source_root, file_name)
        if os.path.isfile(src_path):
            if should_exclude_file(src_path):
                print(f"  [EXCLUDED] {file_name}")
                total_excluded += 1
                continue
            
            dest_path = os.path.join(temp_source_dir, file_name)
            shutil.copy2(src_path, dest_path)
            print(f"  [DONE] copied {file_name}")
            total_included += 1
        else:
            print(f"WARNING: required file not found, skipping: {file_name}")
    
    # Copy requirements.txt.
    requirements_src = os.path.join(source_root, 'requirements.txt')
    if os.path.isfile(requirements_src):
        requirements_dest = os.path.join(temp_source_dir, 'requirements.txt')
        shutil.copy2(requirements_src, requirements_dest)
        print("  [DONE] copied requirements.txt")
        total_included += 1

    # Create the PYZ archive.
    print("\nCreating secure archive...")
    print(f"Summary: included {total_included}, excluded {total_excluded}")
    
    zipapp.create_archive(
        source=temp_source_dir,
        target=target_file,
        interpreter='/usr/bin/env python',
        main=main_entry_point,
        compressed=True
    )
    print(f"Created secure archive: {target_file}")

    # Show archive size.
    if os.path.exists(target_file):
        file_size = os.path.getsize(target_file)
        print(f"Archive size: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")

    # Remove the temporary build directory.
    shutil.rmtree(temp_source_dir)
    print(f"Removed temporary directory: {temp_source_dir}")

def sync_release_support_files():
    """Copy runtime dependencies and the physical Streamlit entry into release."""
    release_dir = Path(target_file).parent
    requirements_src = Path(source_root) / 'requirements.txt'
    shutil.copy2(requirements_src, release_dir / 'requirements.txt')

    frontend_src = Path(source_root) / 'frontend'
    frontend_dest = release_dir / 'frontend'
    if frontend_dest.exists():
        shutil.rmtree(frontend_dest)
    included, excluded = copy_directory_filtered(str(frontend_src), str(frontend_dest))
    print(f"Synced frontend runtime: included {included}, excluded {excluded}")

def create_usage_instructions():
    """Create release usage instructions."""
    usage_file = os.path.join(os.path.dirname(target_file), 'USAGE.txt')
    
    usage_content = f"""FT Data Cleaner - Usage Instructions

Run:
1. Ensure Python 3.10 or later is installed.
2. Install dependencies: python -m pip install -r requirements.txt
3. Start the application: python ft_data_cleaner.pyz

Features:
- Riyuexin: DC, FT scatter charts, DVDS, RG, PAT, and SYL&SBL
- TMS adapters: independent, fail-closed Riyuexin and Riyueguang FT DC routes
- Jiequn: DC-AI, DC-1, DC-unified, DC-3, FT scatter charts, DVDS, RG, PAT, and SYL&SBL
- Dianji: FT-ALL cleaning, FT scatter charts, PAT, and SYL&SBL
- Jijia: NCE15TD120BT STS8203 FT-ALL cleaning to Riyuexin-compatible DC_Data

Notes:
- Jiequn DC-AI is the recommended default and detects one DC format per selected directory.
- Mixed DC-1, DC-unified, and DC-3 directories are rejected instead of guessed.
- For Jiequn DC-3, select the third-line DC1 root or a product directory.
- Dianji FT-ALL uses a format registry to detect verified PowerTECH .xls text, PowerTECH .xlsx Datalog, STS8203 .csv, and DP1205 SW+Trr TF .csv sources, then dispatches to the matching parser module.
- Jijia FT-ALL strictly supports the reviewed NCE15TD120BT GB18030 STS8203 123-column layout. It writes NUM + lot_ID + 117 unit-qualified parameters to DC_Data, excludes PASSFG/SOFT_BIN, and retains both PASS and FAIL records.
- Dianji batch IDs accept the verified C203133.03 week-code and FA65-5405 formats, with strict filename/Lot identity checks.
- Dianji PowerTECH also accepts the reviewed dj6 no-space lot/batch form, -A-A lot suffix, DC M08 test tag, and compact 32-Item program; unknown variants remain rejected.
- Dianji PowerTECH dj8 accepts the reviewed product-less outer filename and optional numeric copy suffix only when DataFileName, the exact approved TestFileName program, and Lot metadata prove one consistent identity.
- Dianji PowerTECH XLSX strictly supports the reviewed NCE40ED120VT(LA) dj7 34/35/38/39-Item layouts and restores one 21-parameter RAW contract; unknown products, layouts, units, Bias conditions, or identities are rejected.
- Dianji TF CSV strictly supports the reviewed NCE40ED120VT(LA) DP1205 SW+Trr 57-column/50-Item layout and writes NUM + batch + 47 unit-qualified parameters; '/' is treated as missing and Udc(V) is the retention gate.
- Dianji FT-ALL stores each run in a numbered product-family folder such as NCEAP016N85LL(M)_001.
- Dianji restores one stable RAW order across both standard Item 29-31 permutations and the reviewed compact 32-Item mapping.
- Dianji STS8203 supports the reviewed NCEAP40T20AGU(M)-7E00 layout, including verified 8/9-digit manufacturing lots, suffix -a, source segment 2, and cross-day tests whose Date matches Ending Time; unreviewed variants are rejected.
- Jiequn cleaning keeps DC-AI plus standalone DVDS/RG buttons: product roots can run the complete bundle, while pure DVDS/RG directories use their specialized cleaners.
- Jiequn standalone DVDS/RG safely recognizes one existing valid cleaned workbook and skips duplicate cleaning; ambiguous result directories are rejected.
- PAT for Riyuexin, Jiequn, and Dianji previews a raw-source directory and calculates directly with bounded memory; no cleaned workbook is required.
- Riyuexin PAT accepts a product root with DC/DVDS/RG subdirectories or one raw type directory. Dianji PAT accepts one registered raw format directory and rejects mixed formats or products.
- SYL&SBL accepts one .xls or .xlsx yield workbook.
- Output files are saved under the selected output directory.
- After a supported Riyuexin, Jiequn, or Dianji cleaning operation succeeds, click FT Scatter Chart to open one chart per parameter.
- Scatter limits and bias conditions come from each source file and use the same output-unit conversion as cleaned measurements.
- Reversed numeric Min/Max values in Jiequn P-type programs are normalized for LSL/USL while retaining the raw cells.
- Scatter colors and the right-side legend identify lot_ID batches.
- Scatter charts use a light theme with enlarged markers, axis numbers, titles, legends, and limit labels.
- Dense repeated in-spec values are compacted for faster opening; every OOS point is retained.
- Review the application log if processing fails.
- TMS may supply a manually confirmed Lot only when an approved filename profile
  is otherwise complete and the Lot field alone is absent. The override never
  changes source files and cannot replace a conflicting parsed Lot.

Version: {VERSION}
Author: cc
"""
    
    with open(usage_file, 'w', encoding='utf-8') as f:
        f.write(usage_content)
    
    print(f"Created usage instructions: {usage_file}")

if __name__ == '__main__':
    print("Building secure FT Data Cleaner release...")
    print("=" * 60)
    create_secure_archive()
    sync_release_support_files()
    create_usage_instructions()
    print("=" * 60)
    print("Secure build completed.")
    print("Sensitive documents and generated data are excluded from the archive.")
    print(f"Output: {target_file}")
