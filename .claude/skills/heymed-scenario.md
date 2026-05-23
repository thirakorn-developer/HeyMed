---
name: heymed-scenario
description: Run a pharmacy scenario simulation — validates the system handles real clinical workflows correctly
---

Run a pharmacy scenario simulation. Pick the scenario from the argument, or run all scenarios if no argument given.

## Available Scenarios

### `prescription` — New Prescription Validation
Simulate receiving a new prescription:
1. Ask which drug (or use argument)
2. Search the drug in NDC database
3. Get full label info (dosing, warnings, contraindications)
4. Check for pregnancy safety
5. Present a "Prescription Validation Report"

### `interaction` — Multi-Drug Interaction Check
Simulate checking a patient's full medication list:
1. Ask for drug list (or use argument, comma-separated)
2. Check all pairwise interactions
3. Get adverse events for each drug
4. Flag dangerous combinations with severity
5. Present an "Interaction Safety Report"

### `substitute` — Generic Substitution
Simulate finding a generic alternative:
1. Ask which brand drug (or use argument)
2. Search the brand in NDC
3. Find alternatives in same class
4. Compare dosage forms and strengths available
5. Present a "Substitution Options Report"

### `counseling` — Patient Counseling
Simulate counseling a patient about their medication:
1. Ask which drug (or use argument)
2. Get dosing info
3. Get common side effects (adverse events)
4. Get pregnancy/nursing info
5. Get warnings
6. Present a "Patient Counseling Guide" in plain language

### `recall` — Safety Alert Check
Simulate checking if any drugs have safety issues:
1. Ask which drugs to check (or use argument)
2. Check recalls for each drug
3. Check adverse events
4. Get warnings
5. Present a "Safety Alert Report"

## Output Format

Each scenario produces a formatted clinical report with:
- Header with scenario name and date
- Sections with findings from MCP tools
- Clinical recommendations based on the data
- Action items for the pharmacist
