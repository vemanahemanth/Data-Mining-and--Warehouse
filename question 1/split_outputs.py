import re
import os

input_file = "full_exam_output.txt"
output_dir = "outputs"

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

with open(input_file, "r", encoding="utf-16") as f:
    content = f.read()

# Define the tasks and their headers to split the file
tasks = [
    ("Task A", "TASK A: STAND UP PLATFORM & LAND DATA"),
    ("Task B", "TASK B: MAKE IT SAFE TO RUN TWICE (IDEMPOTENCY PROOF)"),
    ("Task C", "TASK C: DESIGN AND BUILD TABLES BEHIND THE DASHBOARD"),
    ("Task D", "TASK D: MAKE MARCH USE MARCH'S PRICES (SCD TYPE 2 PRICE REVISIONS)"),
    ("Task E", "TASK E: QUERY ACROSS TWO SYSTEMS (FEDERATED S3 + POSTGRESQL)"),
    ("Task F", "TASK F: FINANCIAL RECONCILIATION & VARIANCE ANALYSIS")
]

for i in range(len(tasks)):
    task_name, header = tasks[i]
    
    # Find the start of the current task
    start_idx = content.find(header)
    if start_idx == -1:
        continue
        
    # Find the start of the next task, or end of file if it's the last task
    if i < len(tasks) - 1:
        next_header = tasks[i+1][1]
        end_idx = content.find(next_header)
        if end_idx == -1:
            end_idx = len(content)
    else:
        end_idx = len(content)
        
    # Extract the block and save it
    task_content = content[start_idx:end_idx].strip()
    
    filename = f"{output_dir}/{task_name.lower().replace(' ', '_')}_output.txt"
    with open(filename, "w", encoding="utf-8") as out_f:
        out_f.write(task_content)
        
print("Successfully split outputs into the 'outputs' directory.")
