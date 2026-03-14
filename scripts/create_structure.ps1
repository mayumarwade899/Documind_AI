Write-Host "Creating Production RAG System folder structure..." -ForegroundColor Cyan

# Helper function to create folder + files
function Create-Module {
    param (
        [string]$folder,
        [string[]]$files
    )
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
    foreach ($file in $files) {
        New-Item -ItemType File -Path "$folder\$file" -Force | Out-Null
    }
}

# Root level files
$rootFiles = @(".env", ".env.example", ".gitignore", "requirements.txt", "README.md")
foreach ($file in $rootFiles) {
    New-Item -ItemType File -Path $file -Force | Out-Null
}

# Config module
Create-Module "config" @("__init__.py", "settings.py", "logging_config.py")

# Ingestion module
Create-Module "ingestion" @("__init__.py", "document_loader.py", "chunker.py", "embedder.py", "pipeline.py")

# Retrieval module
Create-Module "retrieval" @("__init__.py", "vector_store.py", "bm25_retriever.py", "hybrid_retriever.py", "query_rewriter.py", "multi_query.py")

# Reranking module
Create-Module "reranking" @("__init__.py", "cross_encoder.py")

# Generation module
Create-Module "generation" @("__init__.py", "prompt_builder.py", "llm_client.py", "answer_generator.py")

# Verification module
Create-Module "verification" @("__init__.py", "citation_enforcer.py", "answer_verifier.py")

# Evaluation module
Create-Module "evaluation" @("__init__.py", "ragas_evaluator.py", "golden_dataset.py", "ci_gate.py")

# Monitoring module
Create-Module "monitoring" @("__init__.py", "metrics_tracker.py", "feedback_store.py", "logger.py")

# API module
Create-Module "api" @("__init__.py", "main.py", "dependencies.py")
Create-Module "api\routes" @("__init__.py", "query.py", "ingest.py", "feedback.py", "metrics.py")

# Scripts
Create-Module "scripts" @("ingest_documents.py", "run_evaluation.py", "generate_golden.py")

# Data directories
$dataDirs = @(
    "data\documents",
    "data\golden_dataset",
    "data\chroma_db",
    "data\bm25_index",
    "data\feedback",
    "data\metrics"
)
foreach ($dir in $dataDirs) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

# Tests
Create-Module "tests" @("__init__.py", "test_ingestion.py", "test_retrieval.py", "test_generation.py", "test_verification.py", "test_evaluation.py")

Write-Host "Done! Folder structure created." -ForegroundColor Green
Write-Host ""
Write-Host "Your project modules:" -ForegroundColor Yellow
$folders = @("api", "ingestion", "retrieval", "reranking", "generation", "verification", "evaluation", "monitoring", "config", "scripts", "data", "tests")
foreach ($f in $folders) {
    Write-Host "  $f/" -ForegroundColor White
}