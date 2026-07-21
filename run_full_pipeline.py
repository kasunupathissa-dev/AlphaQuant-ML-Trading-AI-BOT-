import subprocess
import sys
from datetime import datetime

def run_pipeline():
    """
    Executes the entire AlphaQuant V5 data and training pipeline in sequence.
    This automates the process of data ingestion, feature engineering, 
    labeling, model training, and validation.
    """
    print("==================================================")
    print(f"  ALPHAQUANT V5: MASTER PIPELINE EXECUTION        ")
    print(f"  [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print("==================================================")

    # The scripts to run, in the exact required order
    pipeline_scripts = [
        ("V5.1 Data Ingestion", "data_ingestion.py"),
        ("V5 Feature Engineering", "feature_generator_v4.py"),
        ("V5 Meta-Labeling", "label_generator_v4.py"),
        ("V5 Calibrated Model Training", "model_training_calibrated.py"),
        ("V5 Institutional Validation", "validation_suite.py")
    ]

    for i, (stage_name, script_name) in enumerate(pipeline_scripts):
        print(f"\n[PIPELINE STAGE {i+1}/{len(pipeline_scripts)}] --- {stage_name} ---")
        
        try:
            # We use sys.executable to ensure that we are using the same Python
            # interpreter (and virtual environment) that this script is running in.
            result = subprocess.run(
                [sys.executable, script_name], 
                check=True,        # This will raise a CalledProcessError if the script returns a non-zero exit code
                capture_output=True, # Capture stdout and stderr
                text=True          # Decode stdout/stderr as text
            )
            
            # Print the output from the script for visibility
            print(result.stdout)
            
            if result.stderr:
                print("--- Script Errors/Warnings ---")
                print(result.stderr)

            print(f"[SUCCESS] Stage '{stage_name}' completed.")

        except FileNotFoundError:
            print(f"[FATAL ERROR] Script '{script_name}' not found. Aborting pipeline.")
            return
        except subprocess.CalledProcessError as e:
            print(f"[FATAL ERROR] Stage '{stage_name}' failed with exit code {e.returncode}.")
            print("--- STDOUT ---")
            print(e.stdout)
            print("--- STDERR ---")
            print(e.stderr)
            print("Aborting pipeline to prevent data corruption.")
            return
        except Exception as e:
            print(f"[FATAL UNHANDLED ERROR] An unexpected error occurred during '{stage_name}': {e}")
            return

    print("\n==================================================")
    print("  MASTER PIPELINE COMPLETED SUCCESSFULLY          ")
    print("==================================================")
    print("New AI models have been trained and validated.")
    print("The system is ready for live deployment.")

if __name__ == "__main__":
    run_pipeline()