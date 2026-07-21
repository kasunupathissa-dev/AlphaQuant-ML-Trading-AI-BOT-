import subprocess
import sys
from datetime import datetime

def run_pipeline():
    """
    Executes the entire AlphaQuant V6 institutional pipeline in sequence.
    """
    print("==================================================")
    print(f"  ALPHAQUANT V6.1: MASTER PIPELINE EXECUTION      ")
    print(f"  [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print("==================================================")

    pipeline_scripts = [
        ("V5.2 Data Ingestion", "data_ingestion.py"),
        ("V6.2 Feature Engineering", "feature_generator_v6.py"),
        ("V6.6 Meta-Labeling", "label_generator_v5.py"),
        ("V6.3 Ensemble Model Training", "model_training_v6.py"),
        ("V6.1 Institutional Validation", "validation_suite_v6.py")
    ]

    for i, (stage_name, script_name) in enumerate(pipeline_scripts):
        print(f"\n[PIPELINE STAGE {i+1}/{len(pipeline_scripts)}] --- {stage_name} ---")
        
        if script_name == "data_ingestion.py":
            print("[INFO] This stage may take several minutes. Please be patient.")

        try:
            result = subprocess.run(
                [sys.executable, script_name], 
                check=True,
                capture_output=True,
                text=True
            )
            
            print(result.stdout)
            
            if result.stderr:
                clean_stderr = "\n".join([line for line in result.stderr.split('\n') if 'DeprecationWarning' not in line and 'LightGBM' not in line])
                if clean_stderr.strip():
                    print("--- Script Errors/Warnings ---")
                    print(clean_stderr)

            print(f"[SUCCESS] Stage '{stage_name}' completed.")

        except FileNotFoundError:
            print(f"[FATAL ERROR] Script '{script_name}' not found. Aborting.")
            return
        except subprocess.CalledProcessError as e:
            print(f"[FATAL ERROR] Stage '{stage_name}' failed.")
            print("--- STDERR ---")
            print(e.stderr)
            print("Aborting pipeline.")
            return
        except KeyboardInterrupt:
            print("\n[FATAL ERROR] Pipeline manually interrupted. Aborting.")
            return
        except Exception as e:
            print(f"[FATAL UNHANDLED ERROR] An unexpected error occurred: {e}")
            return

    print("\n==================================================")
    print("  V6.1 MASTER PIPELINE COMPLETED SUCCESSFULLY     ")
    print("==================================================")
    print("New Ensemble AI models have been trained and validated.")
    print("The system is ready for the final V6 live engine deployment.")

if __name__ == "__main__":
    run_pipeline()