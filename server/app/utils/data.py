from typing import TypedDict


class Metadata(TypedDict):
    doc_id: str
    title: str
    source: str
    keywords: list[str]


data: list[Metadata] = [
    {
        "doc_id": "python-tutorial-control-flow",
        "title": "Python Tutorial - Control Flow",
        "source": "https://raw.githubusercontent.com/python/cpython/main/Doc/tutorial/controlflow.rst",
        "keywords": ["python", "programming languages", "programming"],
    },
    {
        "doc_id": "javascript-guide-introduction-mdn",
        "title": "JavaScript Guide - Introduction (MDN)",
        "source": "https://raw.githubusercontent.com/mdn/content/main/files/en-us/web/javascript/guide/introduction/index.md",
        "keywords": ["javascript", "programming languages", "programming"],
    },
    {
        "doc_id": "typescript-handbook-everyday-types",
        "title": "TypeScript Handbook - Everyday Types",
        "source": "https://raw.githubusercontent.com/microsoft/TypeScript-Website/v2/packages/documentation/copy/en/handbook-v2/Everyday%20Types.md",
        "keywords": ["typescript", "programming languages", "programming"],
    },
    {
        "doc_id": "go-language-specification",
        "title": "Go Language Specification",
        "source": "https://raw.githubusercontent.com/golang/go/master/doc/go_spec.html",
        "keywords": ["go", "programming languages", "programming"],
    },
    {
        "doc_id": "rust-book-what-is-ownership",
        "title": "Rust Book - What Is Ownership?",
        "source": "https://raw.githubusercontent.com/rust-lang/book/main/src/ch04-01-what-is-ownership.md",
        "keywords": ["rust", "programming languages", "memory ownership", "programming"],
    },
    {
        "doc_id": "node-js-http-api-reference",
        "title": "Node.js HTTP API Reference",
        "source": "https://raw.githubusercontent.com/nodejs/node/main/doc/api/http.md",
        "keywords": ["node.js", "javascript", "http", "client-server", "backend"],
    },
    {
        "doc_id": "react-describing-the-ui",
        "title": "React - Describing the UI",
        "source": "https://raw.githubusercontent.com/reactjs/react.dev/main/src/content/learn/describing-the-ui.md",
        "keywords": ["react", "javascript", "component-based ui", "frontend"],
    },
    {
        "doc_id": "fastapi-first-steps-tutorial",
        "title": "FastAPI - First Steps Tutorial",
        "source": "https://raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/tutorial/first-steps.md",
        "keywords": ["fastapi", "python", "rest api", "backend"],
    },
    {
        "doc_id": "docker-hub-quickstart",
        "title": "Docker Hub Quickstart",
        "source": "https://raw.githubusercontent.com/docker/docs/main/content/manuals/docker-hub/quickstart.md",
        "keywords": ["docker", "containers", "infrastructure"],
    },
    {
        "doc_id": "kubernetes-concepts-overview",
        "title": "Kubernetes Concepts Overview",
        "source": "https://raw.githubusercontent.com/kubernetes/website/main/content/en/docs/concepts/overview/_index.md",
        "keywords": ["kubernetes", "container orchestration", "infrastructure"],
    },
    {
        "doc_id": "github-actions-quickstart",
        "title": "GitHub Actions Quickstart",
        "source": "https://raw.githubusercontent.com/github/docs/main/content/actions/get-started/quickstart.md",
        "keywords": ["github actions", "ci/cd", "development"],
    },
    {
        "doc_id": "aws-amazon-s3-developer-guide-overview",
        "title": "AWS - Amazon S3 Developer Guide Overview",
        "source": "https://raw.githubusercontent.com/awsdocs/amazon-s3-developer-guide/master/doc_source/Introduction.md",
        "keywords": ["amazon s3", "aws", "object storage", "data"],
    },
    {
        "doc_id": "azure-microservices-architecture-style",
        "title": "Azure - Microservices Architecture Style",
        "source": "https://raw.githubusercontent.com/MicrosoftDocs/architecture-center/main/docs/guide/architecture-styles/microservices.md",
        "keywords": ["microservices", "architecture"],
    },
    {
        "doc_id": "google-cloud-run-sample-applications",
        "title": "Google Cloud Run - Sample Applications",
        "source": "https://raw.githubusercontent.com/GoogleCloudPlatform/cloud-run-samples/main/README.md",
        "keywords": ["google cloud run", "google cloud", "serverless", "containers", "infrastructure"],
    },
    {
        "doc_id": "tcp-protocol-specification-rfc-9293",
        "title": "TCP Protocol Specification - RFC 9293",
        "source": "https://www.rfc-editor.org/rfc/rfc9293.txt",
        "keywords": ["tcp", "transport protocol", "networking"],
    },
    {
        "doc_id": "http-semantics-rfc-9110",
        "title": "HTTP Semantics - RFC 9110",
        "source": "https://www.rfc-editor.org/rfc/rfc9110.txt",
        "keywords": ["http", "application protocol", "client-server", "networking"],
    },
    {
        "doc_id": "tls-1-3-specification-rfc-8446",
        "title": "TLS 1.3 Specification - RFC 8446",
        "source": "https://www.rfc-editor.org/rfc/rfc8446.txt",
        "keywords": ["tls", "transport security", "security"],
    },
    {
        "doc_id": "dns-implementation-and-specification-rfc-1035",
        "title": "DNS Implementation and Specification - RFC 1035",
        "source": "https://www.rfc-editor.org/rfc/rfc1035.txt",
        "keywords": ["dns", "domain name system", "networking"],
    },
    {
        "doc_id": "postgresql-sql-queries-reference",
        "title": "PostgreSQL - SQL Queries Reference",
        "source": "https://www.postgresql.org/docs/18/queries-table-expressions.html",
        "keywords": ["postgresql", "sql", "relational database", "data"],
    },
    {
        "doc_id": "redis-quick-start-guide",
        "title": "Redis - Quick Start Guide",
        "source": "https://raw.githubusercontent.com/redis/redis/refs/heads/unstable/README.md",
        "keywords": ["redis", "in-memory database", "key-value store", "data"],
    },
    {
        "doc_id": "mongodb-database-setup-and-components",
        "title": "MongoDB - Database Setup and Components",
        "source": "https://raw.githubusercontent.com/mongodb/mongo/master/README.md",
        "keywords": ["mongodb", "document database", "data"],
    },
    {
        "doc_id": "sqlite-source-and-database-overview",
        "title": "SQLite - Source and Database Overview",
        "source": "https://raw.githubusercontent.com/sqlite/sqlite/master/README.md",
        "keywords": ["sqlite", "sql", "relational database", "embedded database", "data"],
    },
    {
        "doc_id": "retrieval-augmented-generation-original-research",
        "title": "Retrieval-Augmented Generation - Original Research",
        "source": "https://ar5iv.labs.arxiv.org/html/2005.11401",
        "keywords": ["retrieval-augmented generation", "ai"],
    },
    {
        "doc_id": "attention-is-all-you-need-transformers",
        "title": "Attention Is All You Need - Transformers",
        "source": "https://ar5iv.labs.arxiv.org/html/1706.03762",
        "keywords": ["transformer", "neural networks", "ai"],
    },
    {
        "doc_id": "hugging-face-transformers-library-guide",
        "title": "Hugging Face Transformers - Library Guide",
        "source": "https://raw.githubusercontent.com/huggingface/transformers/main/README.md",
        "keywords": ["hugging face transformers", "transformer", "machine learning", "ai"],
    },
    {
        "doc_id": "pytorch-deep-learning-framework-guide",
        "title": "PyTorch - Deep Learning Framework Guide",
        "source": "https://raw.githubusercontent.com/pytorch/pytorch/main/README.md",
        "keywords": ["pytorch", "python", "deep learning", "machine learning", "ai"],
    },
    {
        "doc_id": "langchain-llm-application-framework",
        "title": "LangChain - LLM Application Framework",
        "source": "https://raw.githubusercontent.com/langchain-ai/langchain/master/README.md",
        "keywords": ["langchain", "llm applications", "ai"],
    },
    {
        "doc_id": "google-code-review-standard",
        "title": "Google - Code Review Standard",
        "source": "https://raw.githubusercontent.com/google/eng-practices/master/review/reviewer/standard.md",
        "keywords": ["code review", "development"],
    },
    {
        "doc_id": "python-pep-8-coding-style-specification",
        "title": "Python PEP 8 - Coding Style Specification",
        "source": "https://raw.githubusercontent.com/python/peps/main/peps/pep-0008.rst",
        "keywords": ["python", "coding style", "development"],
    },
    {
        "doc_id": "terraform-infrastructure-as-code",
        "title": "Terraform - Infrastructure as Code",
        "source": "https://raw.githubusercontent.com/hashicorp/terraform/main/README.md",
        "keywords": ["terraform", "infrastructure as code", "infrastructure"],
    },
    {
        "doc_id": "ansible-configuration-management",
        "title": "Ansible - Configuration Management",
        "source": "https://raw.githubusercontent.com/ansible/ansible/devel/README.md",
        "keywords": ["ansible", "configuration management", "infrastructure as code", "infrastructure"],
    },
    {
        "doc_id": "prometheus-monitoring-and-metrics",
        "title": "Prometheus - Monitoring and Metrics",
        "source": "https://raw.githubusercontent.com/prometheus/prometheus/main/README.md",
        "keywords": ["prometheus", "monitoring", "metrics", "observability"],
    },
    {
        "doc_id": "grafana-observability-dashboards",
        "title": "Grafana - Observability Dashboards",
        "source": "https://raw.githubusercontent.com/grafana/grafana/main/README.md",
        "keywords": ["grafana", "monitoring", "dashboards", "observability"],
    },
    {
        "doc_id": "opentelemetry-observability-specification",
        "title": "OpenTelemetry - Observability Specification",
        "source": "https://raw.githubusercontent.com/open-telemetry/opentelemetry-specification/main/specification/overview.md",
        "keywords": ["opentelemetry", "telemetry", "observability"],
    },
]
