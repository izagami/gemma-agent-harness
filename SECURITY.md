# Security policy

Report vulnerabilities privately through GitHub's "Report a vulnerability" (Security tab), not in a public issue.

The agent harness runs model-written commands only inside a sandbox container without network access; task checkers
run in their own containers. Model servers (vLLM / llama.cpp) are expected to listen on 127.0.0.1 only. Do not point
the harness at a model endpoint or a task directory you do not trust.
