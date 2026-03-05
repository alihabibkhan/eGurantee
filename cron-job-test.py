from imports import *
from application import application


@application.route('/run-job')
def run_job():
    """This is the endpoint our cron job will call"""
    print("=" * 60)
    print(f"🚀 FLASK CRON JOB STARTED at: {datetime.now().isoformat()}")
    print("=" * 60)

    # Job execution details
    job_results = {
        "status": "success",
        "start_time": datetime.now().isoformat(),
        "job_name": "test-cron-three-times",
        "environment": {}
    }

    # Log system information
    print(f"📊 System: {platform.system()} {platform.release()}")
    print(f"🐍 Python: {sys.version}")
    print(f"📂 Working dir: {os.getcwd()}")

    # Check Render environment
    if os.getenv('RENDER'):
        print("✅ Running on Render!")
        render_info = {
            "service_id": os.getenv('RENDER_SERVICE_ID', 'N/A'),
            "service_name": os.getenv('RENDER_SERVICE_NAME', 'N/A'),
            "instance_id": os.getenv('RENDER_INSTANCE_ID', 'N/A')
        }
        print(f"🆔 Render Service: {render_info}")
        job_results["render_info"] = render_info

    # Simulate some work
    print("\n📝 Performing test tasks...")

    # Task 1: Check memory usage
    try:
        memory = psutil.virtual_memory()
        print(f"💾 Memory usage: {memory.percent}%")
        job_results["memory_usage_percent"] = memory.percent
    except:
        print("💾 Memory info not available")

    # Task 2: List environment variables (non-sensitive ones)
    safe_vars = ['PATH', 'PYTHON_VERSION', 'LANG']
    for var in safe_vars:
        if os.getenv(var):
            print(f"🔧 {var}: {os.getenv(var)}")

    # Task 3: Create a simple log file
    log_entry = f"{datetime.now().isoformat()} - Cron job executed successfully\n"
    try:
        with open('cron_log.txt', 'a') as f:
            f.write(log_entry)
        print("📝 Log file updated: cron_log.txt")
    except:
        print("⚠️ Could not write to log file")

    # Job completion
    end_time = datetime.now().isoformat()
    print(f"\n✅ FLASK CRON JOB COMPLETED at: {end_time}")
    print("=" * 60)

    job_results["end_time"] = end_time
    job_results["duration_seconds"] = (
            datetime.datetime.fromisoformat(end_time) -
            datetime.fromisoformat(job_results["start_time"])
    ).total_seconds()

    return jsonify(job_results)