# Build Agentic AI Applications with Claude Agent SDK and Amazon Bedrock AgentCore

This workshop guides you through building, deploying, and operating AI agents using the Claude Agent SDK and Amazon Bedrock AgentCore.

## Workshop Overview

You will build a **Student Analytics AI Agent** that can query Amazon Athena to analyze student management data through natural language. The workshop demonstrates:

- **Module 0**: Environment setup and configuration
- **Module 1**: Local agent development with Claude Agent SDK
  - 1a: Basic agent without skills (shows limitations)
  - 1b: Enhanced agent with skills and project context (shows power of context engineering)
- **Module 2**: Deploying to Amazon Bedrock AgentCore
- **Module 3**: Observability and monitoring (stretch goal)

## Prerequisites

- AWS Account with Bedrock access (Claude Sonnet model enabled)
- Python 3.14+
- AWS CLI configured with appropriate permissions
- Docker (for AgentCore container deployment)

## Quick Start

1. Clone this repository
2. Set up your environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```
3. Open `module-0-setup/0-environment-setup.ipynb` and follow along

## Project Structure

```
.
├── module-0-setup/
│   └── 0-environment-setup.ipynb          # Environment configuration
├── module-1-local-agent/
│   ├── 1a-basic-agent-no-skills.ipynb     # Basic agent demonstration
│   └── 1b-agent-with-skills.ipynb         # Enhanced agent with skills
├── module-2-agentcore-deployment/
│   └── 2-deploy-to-agentcore.ipynb        # AgentCore deployment
├── module-3-observability/
│   └── 3-agentcore-observability.ipynb    # Monitoring and observability
├── agent/                                  # Agent implementations
│   ├── basic_agent.py                      # Minimal agent
│   ├── skills_agent.py                     # Agent with skills
│   └── agent_agentcore.py                  # AgentCore wrapper
├── tools/                                  # Athena query tools
├── scripts/                                # Setup scripts
├── data/metadata/                          # Table metadata
└── .claude/skills/                         # Agent skills
```

## Learning Objectives

By completing this workshop, you will:

1. Understand how to build AI agents with Claude Agent SDK
2. Learn the importance of context engineering (skills, project context)
3. Deploy agents to production with Amazon Bedrock AgentCore
4. Monitor and observe agent behavior in production

## Key Concepts

### Claude Agent SDK
The SDK provides a framework for building AI agents that can use tools (Read, Write, Bash) to accomplish tasks.

### Skills
Skills are domain-specific knowledge loaded into the agent via `.claude/skills/` directories. They provide:
- Query patterns and examples
- Table references and column names
- Best practices for specific domains

### CLAUDE.md
The project context file that gives the agent understanding of the codebase, available tools, and workflows.

### Amazon Bedrock AgentCore
A managed service for deploying and running AI agents with:
- Isolated microVM execution environment
- Built-in observability
- Secure credential management
- HTTP/MCP/A2A protocols

## Support

For issues or questions, please open an issue in this repository.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
