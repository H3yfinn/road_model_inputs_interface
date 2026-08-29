"""Interactive reviewer charts for missing-value proposals and their evidence."""

from __future__ import annotations

import json
import math

import pandas as pd


PROPOSAL_CHART_COLUMNS = [
    "Proposal ID", "Economy", "Branch Path", "Variable", "Year", "Proposed Value",
    "Scale", "Units", "Estimation Method", "Evidence Count",
    "Cross Validation Median APE", "Comment",
]
EVIDENCE_CHART_COLUMNS = [
    "Proposal ID", "Role", "Evidence Economy", "Evidence Branch Path", "Evidence Value",
]


def _safe_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def build_proposal_comparison_html(proposals: pd.DataFrame, evidence: pd.DataFrame) -> str:
    """Return one Plotly page showing every proposal with its comparison evidence."""
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
*{{box-sizing:border-box}} html{{scroll-behavior:smooth}} body{{margin:0;background:#f4f7fb;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1540px;margin:0 auto;padding:24px}} h1{{margin:0 0 8px;font-size:1.55rem}} h2{{margin:0;font-size:1.28rem}} p{{color:var(--muted);line-height:1.45}}
.intro{{background:white;border:1px solid var(--line);border-radius:12px;box-shadow:0 3px 14px rgba(28,43,66,.06);padding:18px}}
.key{{display:flex;flex-wrap:wrap;gap:14px;margin:10px 0 0;font-size:.84rem;color:var(--muted)}} .dot{{width:10px;height:10px;display:inline-block;margin-right:5px;border-radius:50%}}
.economy-nav{{position:sticky;top:0;z-index:20;display:flex;flex-wrap:wrap;gap:7px;margin:14px 0;padding:10px;background:rgba(244,247,251,.96);border:1px solid var(--line);border-radius:10px;backdrop-filter:blur(5px)}}
.economy-nav a{{color:#164e87;background:white;border:1px solid #b8c8da;border-radius:999px;padding:6px 10px;text-decoration:none;font-size:.82rem;font-weight:700}} .economy-nav a:hover,.economy-nav a:focus{{background:#e7f1fb;outline:none}}
.economy-section{{scroll-margin-top:72px;margin:20px 0 30px}} .economy-heading{{display:flex;align-items:baseline;gap:10px;margin:0 2px 10px}} .economy-heading span{{color:var(--muted);font-size:.84rem}}
.chart-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}} .chart-card{{min-width:0;background:white;border:1px solid var(--line);border-radius:12px;box-shadow:0 3px 14px rgba(28,43,66,.06);padding:12px}} .chart-card.is-wide{{grid-column:1/-1}}
.chart-title{{margin:2px 6px 0;font-size:1rem}} .chart-context{{margin:3px 6px 0;color:var(--muted);font-size:.8rem}} .proposal-chart{{width:100%;min-height:520px}}
@media(max-width:950px){{main{{padding:12px}}.chart-grid{{grid-template-columns:1fr}}.chart-card{{grid-column:1}}.economy-nav{{position:static}}}}
</style>
</head>
<body><main>
<section class="intro"><h1>Missing Mileage and Fuel Economy (efficiency) proposals</h1>
<p>Every proposal is shown below, grouped by economy and variable, so the complete review can be read by scrolling one page. Blue circles are the exact same datapoint in other economies, green triangles are related same-economy inputs used by the method, and red diamonds are the proposed values. Hover any point for its full branch, evidence role, method and validation detail. Stored Mileage values are expanded to km/vehicle/year. Fuel Economy is shown in MJ/100 km, where a lower value means better efficiency.</p>
<div class="key"><span><i class="dot" style="background:#1565c0"></i>Exact-branch peer</span><span><i class="dot" style="background:#2e7d32"></i>Related same-economy input</span><span><i class="dot" style="background:#e53935"></i>Proposed value</span></div></section>
<nav class="economy-nav" id="economy-nav" aria-label="Jump to economy"></nav>
<div id="proposal-overview" data-proposal-overview="all-proposals" aria-label="Proposal comparison scatterplots"></div>
</main>
<script>
const proposals={proposal_json};
const evidence={evidence_json};
const sortText=(a,b)=>String(a).localeCompare(String(b),undefined,{{numeric:true,sensitivity:"base"}});
const unique=values=>Array.from(new Set(values)).sort(sortText);
const shortBranch=path=>String(path).replace(/^Demand\\\\/,"").replaceAll("\\\\"," / ");
const branchTick=path=>String(path).replace(/^Demand\\\\/,"").split("\\\\").map(part=>part.replace(" road","")).join("<br>");
const evidenceById=new Map();
for(const row of evidence){{const id=row["Proposal ID"];if(!evidenceById.has(id))evidenceById.set(id,[]);evidenceById.get(id).push(row);}}
function scaleInfo(proposal){{
  const scaleName=String(proposal.Scale||"").trim().toLowerCase();
  const factor=scaleName.startsWith("thousand")?1000:scaleName.startsWith("million")?1000000:scaleName.startsWith("billion")?1000000000:1;
  return {{factor,units:proposal.Variable==="Mileage"?"km/vehicle/year":(proposal.Units||"value")}};
}}
function jitter(index,count,span){{return count<2?0:span*((2*index/(count-1))-1);}}
function makeElement(tag,className,text){{const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;}}
function renderChart(economy,variable,rows,card){{
  const chart=makeElement("div","proposal-chart");
  chart.setAttribute("aria-label",`${{economy}} ${{variable}} proposal comparison scatterplot`);
  card.appendChild(chart);
  const exactX=[],exactY=[],exactData=[],relatedX=[],relatedY=[],relatedData=[],proposalX=[],proposalY=[],proposalData=[];
  rows.forEach((proposal,index)=>{{
    const scale=scaleInfo(proposal);
    const evidenceRows=evidenceById.get(proposal["Proposal ID"])||[];
    const exact=evidenceRows.filter(row=>row["Evidence Branch Path"]===proposal["Branch Path"]&&row["Evidence Economy"]!==proposal.Economy);
    const exactKeys=new Set(exact.map(row=>`${{row["Evidence Economy"]}}␟${{row["Evidence Branch Path"]}}␟${{row["Evidence Value"]}}`));
    const related=evidenceRows.filter(row=>["estimate_input","economy_adjustment_ratio"].includes(row.Role)&&!exactKeys.has(`${{row["Evidence Economy"]}}␟${{row["Evidence Branch Path"]}}␟${{row["Evidence Value"]}}`));
    exact.forEach((row,pointIndex)=>{{exactX.push(index+jitter(pointIndex,exact.length,.28));exactY.push(scale.factor*row["Evidence Value"]);exactData.push([proposal["Proposal ID"],row["Evidence Economy"],shortBranch(row["Evidence Branch Path"]),row.Role]);}});
    related.forEach((row,pointIndex)=>{{relatedX.push(index+jitter(pointIndex,related.length,.18));relatedY.push(scale.factor*row["Evidence Value"]);relatedData.push([proposal["Proposal ID"],row["Evidence Economy"],shortBranch(row["Evidence Branch Path"]),row.Role]);}});
    proposalX.push(index);proposalY.push(scale.factor*proposal["Proposed Value"]);proposalData.push([proposal["Proposal ID"],shortBranch(proposal["Branch Path"]),String(proposal["Estimation Method"]).replaceAll("_"," "),proposal["Evidence Count"],100*Number(proposal["Cross Validation Median APE"]),proposal.Comment]);
  }});
  const traces=[];
  if(exactX.length)traces.push({{name:"Exact-branch peers",x:exactX,y:exactY,mode:"markers",marker:{{color:"#1565c0",size:7,opacity:.72}},customdata:exactData,hovertemplate:"Proposal: %{{customdata[0]}}<br>Evidence economy: %{{customdata[1]}}<br>%{{customdata[2]}}<br>Value: %{{y:,.4g}}<br>Role: %{{customdata[3]}}<extra></extra>"}});
  if(relatedX.length)traces.push({{name:"Related same-economy inputs",x:relatedX,y:relatedY,mode:"markers",marker:{{color:"#2e7d32",size:8,symbol:"triangle-up",opacity:.76}},customdata:relatedData,hovertemplate:"Proposal: %{{customdata[0]}}<br>Evidence economy: %{{customdata[1]}}<br>%{{customdata[2]}}<br>Value: %{{y:,.4g}}<br>Role: %{{customdata[3]}}<extra></extra>"}});
  traces.push({{name:"Proposed value",x:proposalX,y:proposalY,mode:"markers",marker:{{color:"#e53935",size:13,symbol:"diamond",line:{{color:"#8e1512",width:1}}}},customdata:proposalData,hovertemplate:"Proposal: %{{customdata[0]}}<br>%{{customdata[1]}}<br>Proposed: %{{y:,.4g}}<br>Method: %{{customdata[2]}}<br>Evidence rows: %{{customdata[3]}}<br>Cross-validation median error: %{{customdata[4]:.1f}}%<br>%{{customdata[5]}}<extra></extra>"}});
  const units=scaleInfo(rows[0]).units;
  Plotly.newPlot(chart,traces,{{template:"plotly_white",showlegend:false,xaxis:{{tickmode:"array",tickvals:rows.map((_,index)=>index),ticktext:rows.map(row=>branchTick(row["Branch Path"])),tickfont:{{size:9}}}},yaxis:{{title:`${{variable}} (${{units}})`,rangemode:"tozero"}},margin:{{l:84,r:24,t:28,b:145}},height:520,hovermode:"closest"}},{{responsive:true,displaylogo:false}});
}}
function renderEconomySection(economy){{
  const section=makeElement("section","economy-section");section.id=`economy-${{economy}}`;
  const economyRows=proposals.filter(row=>row.Economy===economy);
  const heading=makeElement("div","economy-heading");heading.append(makeElement("h2","",economy),makeElement("span","",`${{economyRows.length}} proposals`));section.appendChild(heading);
  const grid=makeElement("div","chart-grid");section.appendChild(grid);
  for(const variable of ["Mileage","Fuel Economy"]){{
    const rows=economyRows.filter(row=>row.Variable===variable).sort((a,b)=>sortText(a["Branch Path"],b["Branch Path"]));
    if(!rows.length)continue;
    const card=makeElement("article",`chart-card${{rows.length>6?" is-wide":""}}`);
    card.append(makeElement("h3","chart-title",variable),makeElement("p","chart-context",`${{rows.length}} proposed datapoints · base year ${{rows[0].Year}} · hover points for evidence and method details`));grid.appendChild(card);
    renderChart(economy,variable,rows,card);
  }}
  return section;
}}
const economies=unique(proposals.map(row=>row.Economy));
const nav=document.getElementById("economy-nav");
const overview=document.getElementById("proposal-overview");
for(const economy of economies){{const link=makeElement("a","",economy);link.href=`#economy-${{economy}}`;nav.appendChild(link);overview.appendChild(renderEconomySection(economy));}}
</script></body></html>
"""
