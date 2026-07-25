import subprocess
import sys
from datetime import datetime

def run_pipeline():
    """
    Executes the entire AlphaQuant V8 Shotgun pipeline in sequence.
    """
    print("==================================================")
    print(f"  ALPHAQUANT V8: SHOTGUN PIPELINE EXECUTION       ")
    print(f"  [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print("==================================================")

    pipeline_scripts = [
        ("V5.2 Data Ingestion", "data_ingestion.py"),
        ("V7.0 Shotgun Feature Engineering", "feature_generator_v7.py"),
        ("V6.0 Shotgun Meta-Labeling", "label_generator_v6.py"),
        ("V7.0 Shotgun Model Training", "model_training_v7.py"),
        ("V8.0 Shotgun Validation", "validation_suite_v8.py")
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
    print("  V8 SHOTGUN PIPELINE COMPLETED SUCCESSFULLY      ")
    print("==================================================")
    print("New Shotgun AI models have been trained and validated.")
    print("The system is ready for final review before deployment.")

if __name__ == "__main__":
    run_pipeline()