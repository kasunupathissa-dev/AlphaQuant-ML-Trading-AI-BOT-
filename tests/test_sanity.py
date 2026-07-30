import unittest
import os
import re
import pandas as pd

class TestSanity(unittest.TestCase):
    def test_pandas_version(self):
        # Ensure pandas version is printed
        print(f"Active Pandas Version: {pd.__version__}")
        self.assertTrue(hasattr(pd, '__version__'))
        
    def test_no_uppercase_resample_frequency_aliases(self):
        # Find all python files in project
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        uppercase_pattern = re.compile(r"\.resample\(['\"](\d+)?([A-Z])['\"]\)")
        
        flagged_files = []
        for root, dirs, files in os.walk(root_dir):
            # Skip virtual environment and git folders
            if any(ignored in root for ignored in ("aq_env", ".git", "__pycache__", ".venv")):
                continue
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    if "test_sanity.py" in filepath:
                        continue
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        for idx, line in enumerate(f, 1):
                            match = uppercase_pattern.search(line)
                            if match:
                                # Skip feature_generator_v6.py since it's legacy
                                if "feature_generator_v6.py" in filepath:
                                    continue
                                flagged_files.append((file, idx, line.strip()))
                                
        self.assertEqual(len(flagged_files), 0, f"Found deprecated uppercase resample aliases: {flagged_files}")

    def test_no_chained_inplace_assignments(self):
        # Chained inplace pattern e.g. df['col'].fillna(..., inplace=True)
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        chained_pattern = re.compile(r"\[['\"].*['\"]\]\..*inplace=True")
        
        flagged_files = []
        for root, dirs, files in os.walk(root_dir):
            if any(ignored in root for ignored in ("aq_env", ".git", "__pycache__", ".venv")):
                continue
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    if "test_sanity.py" in filepath:
                        continue
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        for idx, line in enumerate(f, 1):
                            if chained_pattern.search(line):
                                flagged_files.append((file, idx, line.strip()))
                                
        self.assertEqual(len(flagged_files), 0, f"Found deprecated chained inplace assignments: {flagged_files}")

if __name__ == '__main__':
    unittest.main()
