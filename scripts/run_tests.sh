#!/bin/bash
# Run pytest with coverage
echo "Running tests with coverage..."
coverage run -m pytest tests/test_app.py tests/test_database_services.py tests/test_integration.py tests/test_auth.py tests/test_auth_views.py
# Specify folders to omitted from coverage check
OMIT_PATTERN="tests/*,venv/*"
# Check if the tests passed
if [ $? -eq 0 ]; then
    echo "✅ Tests passed."
    # Enforce 100% coverage
    echo "Checking for 100% coverage..."
    coverage report --fail-under=100 -m --omit="$OMIT_PATTERN"
    if [ $? -ne 0 ]; then
        echo "❌ Coverage is below 100%. Please improve test coverage."
        coverage html
        echo "HTML report generated at: htmlcov/index.html"
        exit 1
    else
        echo "✅ 100% test coverage achieved!"
        coverage html
        echo "HTML report generated at: htmlcov/index.html"
    fi
else
    echo "❌ Some tests failed. Please fix them before continuing."
    exit 1
fi