---
name: heymed-status
description: Show current status of HeyMed system — DB stats, API health, MCP server tools, and backend status
---

Check the current status of the HeyMed Pharmacy AI system:

1. **Database**: Call `get_ndc_stats` MCP tool to verify FDA NDC data is loaded
2. **Backend**: Check if FastAPI server is running at http://localhost:8000/health using Bash `curl`
3. **PostgreSQL**: Check docker container status using `docker compose ps`
4. **MCP Tools**: List all available HeyMed MCP tools and count them
5. **Data Sources**: Verify each external API is reachable:
   - RxNorm API: `curl -s https://rxnav.nlm.nih.gov/REST/version.json`
   - OpenFDA: `curl -s "https://api.fda.gov/drug/label.json?limit=1" -o /dev/null -w "%{http_code}"`
   - DailyMed: `curl -s "https://dailymed.nlm.nih.gov/dailymed/services/v2/drugnames.json?drug_name=test" -o /dev/null -w "%{http_code}"`

Present results as a status dashboard:
```
HeyMed System Status
━━━━━━━━━━━━━━━━━━━
PostgreSQL:  ✅/❌
FastAPI:     ✅/❌
MCP Server:  ✅/❌ (X tools)
NDC Data:    ✅/❌ (X products, Y packages)
RxNorm API:  ✅/❌
OpenFDA API: ✅/❌
DailyMed API:✅/❌
```
