FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY templates ./templates
COPY config ./config
COPY examples ./examples
COPY knowledge ./knowledge
COPY langgraph.json ./

RUN pip install --no-cache-dir ".[llm]"

# Fail closed until an explicit provider is supplied at runtime.
ENV P2P_LLM_MODE=required
CMD ["python", "-m", "patch2proof.cli", "--help"]
