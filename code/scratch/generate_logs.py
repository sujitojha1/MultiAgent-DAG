import json
import os
from pathlib import Path

# Absolute paths
WORKSPACE_ROOT = Path(__file__).parent.parent.parent
SESSIONS_ROOT = WORKSPACE_ROOT / "code" / "state" / "sessions"
LOGS_DIR = WORKSPACE_ROOT / "logs"

def generate_log(session_id, output_filename, title):
    session_dir = SESSIONS_ROOT / session_id
    if not session_dir.exists():
        print(f"Session {session_id} not found at {session_dir}.")
        return
    
    # Read query
    query_file = session_dir / "query.txt"
    query = query_file.read_text(encoding='utf-8', errors='replace').strip() if query_file.exists() else "Unknown query"
    
    # Read nodes
    nodes_dir = session_dir / "nodes"
    node_files = sorted(nodes_dir.glob("n_*.json"))
    
    log_content = []
    log_content.append(f"# Session Log: {title}")
    log_content.append(f"- **Session ID**: `{session_id}`")
    log_content.append(f"- **User Query**: \"{query}\"")
    log_content.append("")
    log_content.append("## Node Execution Sequence")
    log_content.append("")
    
    for nf in node_files:
        data = json.loads(nf.read_text(encoding='utf-8', errors='replace'))
        node_id = data.get("node_id")
        skill = data.get("skill")
        status = data.get("status")
        inputs = data.get("inputs", [])
        result = data.get("result") or {}
        elapsed = result.get("elapsed_s")
        elapsed_str = f"{elapsed:.2f}s" if elapsed is not None else "N/A"
        provider = result.get("provider") or "N/A"
        output = result.get("output")
        error = result.get("error")
        
        log_content.append(f"### Node `{node_id}` - Skill: `{skill}`")
        log_content.append(f"- **Status**: {status}")
        log_content.append(f"- **Elapsed Time**: {elapsed_str}")
        log_content.append(f"- **Provider**: {provider}")
        log_content.append(f"- **Inputs**: {inputs}")
        
        if error:
            log_content.append(f"- **Error**: `{error}`")
            
        if output:
            log_content.append("- **Output**:")
            # If output has final_answer, code, findings, or stdout, let's extract them
            if isinstance(output, dict):
                if "final_answer" in output:
                    log_content.append(f"  * **Final Answer**:\n    ```\n    {output['final_answer']}\n    ```")
                if "code" in output:
                    log_content.append(f"  * **Generated Code**:\n    ```python\n    {output['code']}\n    ```")
                if "rationale" in output:
                    log_content.append(f"  * **Rationale**: {output['rationale']}")
                if "findings" in output:
                    log_content.append(f"  * **Findings**:\n    ```\n    {output['findings']}\n    ```")
                if "stdout" in output:
                    log_content.append(f"  * **Stdout**:\n    ```\n    {output['stdout']}\n    ```")
                if "exit_code" in output:
                    log_content.append(f"  * **Exit Code**: {output['exit_code']}")
                # If it's a planner node, summarize the planned nodes
                if "nodes" in output:
                    log_content.append("  * **Planned DAG Nodes**:")
                    for pn in output["nodes"]:
                        log_content.append(f"    * Label: `{pn.get('metadata', {}).get('label')}` | Skill: `{pn.get('skill')}` | Inputs: {pn.get('inputs')}")
            else:
                log_content.append(f"  ```\n  {output}\n  ```")
        log_content.append("")
        log_content.append("---")
        log_content.append("")
        
    LOGS_DIR.mkdir(exist_ok=True)
    (LOGS_DIR / output_filename).write_text("\n".join(log_content), encoding='utf-8')
    print(f"Generated {output_filename} in logs/")

if __name__ == "__main__":
    generate_log("s8-2fdd6fdd", "part1_hello.md", "Part 1 - Say Hello Query")
    generate_log("s8-45d05fd5", "part1_shannon.md", "Part 1 - Claude Shannon Biography Query")
    generate_log("s8-f83281eb", "part1_nonexistent_path.md", "Part 1 - Graceful Failure on Nonexistent Path")
    generate_log("s8-03ce0c25", "part1_resume.md", "Part 1 - Lagos/Cairo/Kinshasa Resume Guarantee")
    generate_log("s8-e742b7c9", "part2_parallel_fanout.md", "Part 2 - Parallel Fan-Out (Populations)")
    generate_log("s8-7b05deec", "part3_critic_recovery.md", "Part 3 - Critic Verdict Fail & Recovery Planner Splicing")
    generate_log("s8-b71eb7c6", "part4_coder_trending_metrics.md", "Part 4 - Coder Skill & Sandbox Execution")
    generate_log("s8-4c64a855", "part5_new_skill.md", "Part 5 - New Skill (github_research)")
    generate_log("s8-fccd9e5b", "part6_cpp_trending.md", "Part 6 - github_research on C++ (distiller relevance + critic PASS)")
