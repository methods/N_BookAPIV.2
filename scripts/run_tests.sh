#!/bin/bash
# Run pytest with coverage
echo "Running tests with coverage..."
coverage run -m pytest tests/test_app.py tests/test_mongo_helper.py tests/test_integration.py
# Check if the tests passed
if [ $? -eq 0 ]; then
    echo "✅ Tests passed."
    # Generate terminal coverage report
    echo "Generating coverage report..."
    coverage report -m
    # Enforce 100% coverage
    echo "Checking for 100% coverage..."
    coverage report --fail-under=100 -m
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