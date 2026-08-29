"""Interactive reviewer chart for missing-value proposals and their evidence."""

from __future__ import annotations

import json
import math

import pandas as pd


PROPOSAL_CHART_COLUMNS = [
    "Proposal ID",
    "Economy",
    "Branch Path",
    "Variable",
    "Year",
    "Proposed Value",
    "Scale",
    "Units",
    "Estimation Method",
    "Evidence Count",
    "Cross Validation Median APE",
    "Comment",
]
EVIDENCE_CHART_COLUMNS = [
    "Proposal ID",
    "Role",
    "Evidence Economy",
    "Evidence Branch Path",
    "Evidence Value",
]


def _safe_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def build_proposal_comparison_html(proposals: pd.DataFrame, evidence: pd.DataFrame) -> str:
    """Return a standalone Plotly review page using the model dashboard's dot-plot idiom."""
    missing_proposals = [column for column in PROPOSAL_CHART_COLUMNS if column not in proposals.columns]
    missing_evidence = [column for column in EVIDENCE_CHART_COLUMNS if column not in evidence.columns]
    if missing_proposals or missing_evidence:
        raise ValueError(
            f"Comparison chart inputs are missing columns: proposals={missing_proposals}, "
            f"evidence={missing_evidence}."
        )
    chart_proposals = proposals[PROPOSAL_CHART_COLUMNS].copy()
    chart_evidence = evidence[EVIDENCE_CHART_COLUMNS].copy()
    if chart_proposals.empty or chart_proposals["Proposal ID"].duplicated().any():
        raise ValueError("Comparison chart requires unique, non-empty proposal rows.")
    proposal_ids = set(chart_proposals["Proposal ID"].astype(str))
    evidence_ids = set(chart_evidence["Proposal ID"].astype(str))
    unknown_evidence = evidence_ids - proposal_ids
    if unknown_evidence:
        raise ValueError(f"Comparison evidence contains unknown proposal IDs: {sorted(unknown_evidence)[:5]}")
    missing_evidence = proposal_ids - evidence_ids
    if missing_evidence:
        raise ValueError(f"Comparison proposals have no evidence rows: {sorted(missing_evidence)[:5]}")
    for frame, column in [(chart_proposals, "Proposed Value"), (chart_evidence, "Evidence Value")]:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if numeric.isna().any() or not numeric.map(math.isfinite).all() or not numeric.gt(0).all():
            raise ValueError(f"Comparison chart {column} values must be positive and finite.")
        frame[column] = numeric.astype(float)

    proposal_json = _safe_json(chart_proposals.to_dict("records"))
    evidence_json = _safe_json(chart_evidence.to_dict("records"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Module 1 missing-value proposal comparison</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root{{--ink:#172033;--muted:#5f6b7a;--line:#dbe3ec;--blue:#1565c0;--red:#e53935;--green:#2e7d32}}
*{{box-sizing:border-box}} body{{margin:0;background:#f4f7fb;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1500px;margin:0 auto;padding:24px}} h1{{margin:0 0 8px;font-size:1.55rem}} p{{color:var(--muted);line-height:1.45}}
.card{{background:white;border:1px solid var(--line);border-radius:12px;box-shadow:0 3px 14px rgba(28,43,66,.06);padding:18px;margin-top:16px}}
.controls{{display:grid;grid-template-columns:minmax(140px,.7fr) minmax(160px,.8fr) minmax(300px,2fr);gap:12px}}
label{{font-size:.78rem;font-weight:700;color:#334155}} select{{display:block;width:100%;margin-top:5px;border:1px solid #b9c5d3;border-radius:7px;background:white;padding:9px;font:inherit}}
#comparison-chart{{width:100%;min-height:560px}} .summary{{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:10px;margin-top:12px}}
.metric{{border-left:3px solid var(--blue);background:#f8fafc;padding:10px 12px}} .metric b{{display:block;font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}} .metric span{{display:block;margin-top:4px;font-weight:650}}
.note{{margin-top:12px;border-top:1px solid var(--line);padding-top:12px;color:#425066;font-size:.9rem}}
.key{{display:flex;flex-wrap:wrap;gap:12px;margin:8px 0 0;font-size:.82rem;color:var(--muted)}} .dot{{width:10px;height:10px;display:inline-block;margin-right:5px;border-radius:50%}}
@media(max-width:800px){{main{{padding:12px}}.controls,.summary{{grid-template-columns:1fr}}}}
</style>
</head>
<body><main>
<h1>Missing Mileage and Fuel Economy (efficiency) proposals</h1>
<p>Select an economy, variable and datapoint. The chart compares the proposed value with the exact same branch in other economies and, where used by the Mileage method, related inputs from the target economy. This follows the dashboard's spread-dot convention; hover any point for full detail. Stored Mileage values are expanded to km/vehicle/year. Fuel Economy is shown in MJ/100 km, where a lower value means better efficiency.</p>
<div class="key"><span><i class="dot" style="background:#1565c0"></i>Exact-branch peer</span><span><i class="dot" style="background:#2e7d32"></i>Related same-economy input</span><span><i class="dot" style="background:#e53935"></i>Proposed value</span></div>
<section class="card"><div class="controls">
<label>Economy<select id="economy-select"></select></label>
<label>Variable<select id="variable-select"></select></label>
<label>Datapoint<select id="proposal-select"></select></label>
</div></section>
<section class="card"><div id="comparison-chart" aria-label="Proposal comparison scatterplot"></div>
<div class="summary">
<div class="metric"><b>Proposed value</b><span id="summary-value"></span></div>
<div class="metric"><b>Method</b><span id="summary-method"></span></div>
<div class="metric"><b>Estimate inputs</b><span id="summary-evidence"></span></div>
<div class="metric"><b>Cross-validation median error</b><span id="summary-error"></span></div>
</div><div class="note" id="summary-comment"></div></section>
</main>
<script>
const proposals={proposal_json};
const evidence={evidence_json};
const byId=new Map(proposals.map(row=>[row["Proposal ID"],row]));
const economySelect=document.getElementById("economy-select");
const variableSelect=document.getElementById("variable-select");
const proposalSelect=document.getElementById("proposal-select");
const sortText=(a,b)=>String(a).localeCompare(String(b),undefined,{{numeric:true,sensitivity:"base"}});
const unique=values=>Array.from(new Set(values)).sort(sortText);
const shortBranch=path=>String(path).replace(/^Demand\\\\/,"").replaceAll("\\\\"," / ");
function fillSelect(select,values,selected,labelFn=value=>value){{
  select.replaceChildren(...values.map(value=>{{const option=document.createElement("option");option.value=value;option.textContent=labelFn(value);return option;}}));
  if(values.includes(selected)) select.value=selected;
}}
function refreshVariables(){{
  const values=unique(proposals.filter(row=>row.Economy===economySelect.value).map(row=>row.Variable));
  fillSelect(variableSelect,values,variableSelect.value);
  refreshProposals();
}}
function refreshProposals(){{
  const rows=proposals.filter(row=>row.Economy===economySelect.value&&row.Variable===variableSelect.value).sort((a,b)=>sortText(a["Branch Path"],b["Branch Path"]));
  const selected=rows.some(row=>row["Proposal ID"]===proposalSelect.value)?proposalSelect.value:(rows[0]&&rows[0]["Proposal ID"]);
  fillSelect(proposalSelect,rows.map(row=>row["Proposal ID"]),selected,id=>shortBranch(byId.get(id)["Branch Path"]));
  render();
}}
function render(){{
  const proposal=byId.get(proposalSelect.value);if(!proposal)return;
  const scaleName=String(proposal.Scale||"").trim().toLowerCase();
  const factor=scaleName.startsWith("thousand")?1000:scaleName.startsWith("million")?1000000:scaleName.startsWith("billion")?1000000000:1;
  const displayUnits=proposal.Variable==="Mileage"?"km/vehicle/year":(proposal.Units||"value");
  const rows=evidence.filter(row=>row["Proposal ID"]===proposal["Proposal ID"]);
  const exact=rows.filter(row=>row["Evidence Branch Path"]===proposal["Branch Path"]&&row["Evidence Economy"]!==proposal.Economy);
  const exactKeys=new Set(exact.map(row=>`${{row["Evidence Economy"]}}\u241f${{row["Evidence Branch Path"]}}\u241f${{row["Evidence Value"]}}`));
  const related=rows.filter(row=>["estimate_input","economy_adjustment_ratio"].includes(row.Role)&&!exactKeys.has(`${{row["Evidence Economy"]}}\u241f${{row["Evidence Branch Path"]}}\u241f${{row["Evidence Value"]}}`));
  const traces=[];
  if(exact.length)traces.push({{name:"Exact-branch peers",x:exact.map(row=>row["Evidence Economy"]),y:exact.map(row=>factor*row["Evidence Value"]),mode:"markers",marker:{{color:"#1565c0",size:9}},customdata:exact.map(row=>[row["Evidence Economy"],shortBranch(row["Evidence Branch Path"]),row.Role]),hovertemplate:"Economy: %{{customdata[0]}}<br>%{{customdata[1]}}<br>Value: %{{y:,.4g}}<br>Role: %{{customdata[2]}}<extra></extra>"}});
  if(related.length)traces.push({{name:"Related same-economy inputs",x:related.map(()=>proposal.Economy+" related"),y:related.map(row=>factor*row["Evidence Value"]),mode:"markers",marker:{{color:"#2e7d32",size:10,symbol:"triangle-up"}},customdata:related.map(row=>[row["Evidence Economy"],shortBranch(row["Evidence Branch Path"]),row.Role]),hovertemplate:"Economy: %{{customdata[0]}}<br>%{{customdata[1]}}<br>Value: %{{y:,.4g}}<br>Role: %{{customdata[2]}}<extra></extra>"}});
  const proposedValue=factor*proposal["Proposed Value"];
  traces.push({{name:"Proposed value",x:[proposal.Economy],y:[proposedValue],mode:"markers",marker:{{color:"#e53935",size:17,symbol:"diamond",line:{{color:"#8e1512",width:1}}}},customdata:[[proposal.Economy,shortBranch(proposal["Branch Path"]),proposal["Estimation Method"]]],hovertemplate:"Economy: %{{customdata[0]}}<br>%{{customdata[1]}}<br>Proposed: %{{y:,.4g}}<br>Method: %{{customdata[2]}}<extra></extra>"}});
  Plotly.react("comparison-chart",traces,{{template:"plotly_white",title:{{text:`${{proposal.Variable}} — ${{shortBranch(proposal["Branch Path"])}} (${{proposal.Year}})`,x:.01,xanchor:"left"}},xaxis:{{title:"Economy / evidence group",categoryorder:"category ascending",tickangle:-35}},yaxis:{{title:`${{proposal.Variable}} (${{displayUnits}})`,rangemode:"tozero"}},legend:{{orientation:"h",x:0,y:1.13}},margin:{{l:80,r:25,t:105,b:125}},height:590,hovermode:"closest",shapes:[{{type:"line",xref:"paper",x0:0,x1:1,y0:proposedValue,y1:proposedValue,line:{{color:"#e53935",width:1,dash:"dot"}}}}]}},{{responsive:true,displaylogo:false}});
  document.getElementById("summary-value").textContent=`${{Number(proposedValue).toLocaleString(undefined,{{maximumSignificantDigits:6}})}} ${{displayUnits}}`;
  document.getElementById("summary-method").textContent=String(proposal["Estimation Method"]).replaceAll("_"," ");
  document.getElementById("summary-evidence").textContent=String(proposal["Evidence Count"]);
  document.getElementById("summary-error").textContent=`${{(100*Number(proposal["Cross Validation Median APE"])).toFixed(1)}}%`;
  document.getElementById("summary-comment").textContent=proposal.Comment;
}}
economySelect.addEventListener("change",refreshVariables);variableSelect.addEventListener("change",refreshProposals);proposalSelect.addEventListener("change",render);
fillSelect(economySelect,unique(proposals.map(row=>row.Economy)));refreshVariables();
</script></body></html>
"""
