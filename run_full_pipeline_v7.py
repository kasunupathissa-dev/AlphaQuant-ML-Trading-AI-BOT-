import subprocess
import sys
from datetime import datetime

def run_pipeline():
    """
    Executes the entire AlphaQuant V7 institutional pipeline in sequence.
    This version uses the hardened V7 validation suite.
    """
    print("==================================================")
    print(f"  ALPHAQUANT V7: MASTER PIPELINE EXECUTION        ")
    print(f"  [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print("==================================================")

    # 🟢 V7.0 Upgrade: The full V7 pipeline, from data to hardened validation
    pipeline_scripts = [
        ("V5.2 Data Ingestion", "data_ingestion.py"),
        ("V6.5 Feature Engineering", "feature_generator_v6.py"),
        ("V6.6 Meta-Labeling", "label_generator_v5.py"),
        ("V6.5 Ensemble Model Training", "model_training_v6.py"),
        ("V7.0 Institutional Validation", "validation_suite_v7.py") # <-- Updated to V7
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
                text=True,
                timeout=3600 # 1-hour timeout for the entire stage
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
        except subprocess.TimeoutExpired:
            print(f"[FATAL ERROR] Stage '{stage_name}' timed out after 1 hour. Aborting.")
            return
        except KeyboardInterrupt:
            print("\n[FATAL ERROR] Pipeline manually interrupted. Aborting.")
            return
        except Exception as e:
            print(f"[FATAL UNHANDLED ERROR] An unexpected error occurred: {e}")
            return

    print("\n==================================================")
    print("  V7 MASTER PIPELINE COMPLETED SUCCESSFULLY       ")
    print("==================================================")
    print("New Ensemble AI models have been trained and validated using the hardened V7 suite.")
    print("The system is ready for final review before deployment.")

if __name__ == "__main__":
    run_pipeline()