#!/usr/bin/env python3
"""Build golden/labeller.html: an offline, one-ticket-at-a-time labelling page.

Optional alternative to editing labels_A.csv / labels_B.csv in a spreadsheet
(the README warns Excel can corrupt them). The page shows golden/candidates.csv
one ticket at a time with the protocol's category definitions, keyboard
shortcuts, and autosave in the browser. "Export" downloads labels_<A|B>.csv in
exactly the same columns as the blank sheets (row,label,confidence,notes,narrative),
so tools/agreement.py and tools/merge_golden.py read it unchanged.
Source labels are never embedded.

    python3 tools/make_labeller.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

csv.field_size_limit(10 ** 9)
ROOT = Path(__file__).resolve().parents[1]

CATS = [
    ["Credit reporting", "Credit files/reports/scores, bureaus & furnishers: wrong tradelines, disputes, hard inquiries, ID theft on a report. Harm is to the RECORD."],
    ["Debt collection", "Conduct of collecting an alleged debt: calls, threats, validation, debt not owed/paid/time-barred. Someone is PURSUING the consumer."],
    ["Mortgage", "Loans secured by real property: origination, escrow, servicing, modification, forbearance, foreclosure, PMI, HELOC."],
    ["Credit card", "Revolving card accounts: APR/fees, billing disputes, chargebacks, rewards, limits, unauthorised card charges, store cards."],
    ["Bank account or service", "Deposit accounts & everyday banking: checking/savings, overdraft/NSF, holds, bank closing account, debit card, ATM, CDs."],
    ["Consumer loan", "Closed-end non-mortgage credit: auto loans/leases, personal & instalment loans, student loans, title/payday instalment."],
    ["Money transfer or service", "Moving money: wires, remittances, P2P apps, prepaid/gift cards, virtual currency, money orders, scams via a transfer."],
]

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Golden Set Labeller</title><style>
:root{--bg:#f6f7f9;--fg:#1d2733;--mut:#5b6672;--acc:#1f4e79;--card:#fff;--bd:#d9dee5;--warn:#9a3412}
@media (prefers-color-scheme:dark){:root{--bg:#14181d;--fg:#e6e9ee;--mut:#9aa5b1;--acc:#6aa5df;--card:#1d232a;--bd:#2f3742;--warn:#fdba74}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,"Segoe UI",sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:16px;display:grid;grid-template-columns:1fr 340px;gap:16px}
@media(max-width:860px){.wrap{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:16px}
#txt{white-space:pre-wrap;font-size:16px;max-height:52vh;overflow:auto;margin-top:12px}
button{font:inherit;cursor:pointer;border:1px solid var(--bd);border-radius:8px;background:var(--card);color:var(--fg);padding:7px 12px}
button.cat{display:block;width:100%;text-align:left;margin:6px 0 2px;padding:8px 10px}
button.cat.sel,button.primary{background:var(--acc);color:#fff;border-color:var(--acc)}
.k{display:inline-block;min-width:20px;font-weight:700;color:var(--mut)}button.sel .k{color:#fff}
.def{font-size:12.5px;color:var(--mut);margin:0 0 4px 28px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px}
input,select{font:inherit;background:var(--card);color:var(--fg);border:1px solid var(--bd);border-radius:6px;padding:6px}
.bar{height:6px;background:var(--bd);border-radius:3px;overflow:hidden;margin-top:8px}.bar>div{height:100%;background:var(--acc)}
small,.mut{color:var(--mut)}.warn{color:var(--warn);font-weight:600}
</style></head><body>
<div class="wrap"><div>
<div class="card" id="setup"><h2 style="margin:0 0 8px">Golden set labeller &middot; Group P2-9</h2>
<p class="mut" style="margin:0 0 10px">__N__ tickets from <code>golden/candidates.csv</code>. Read <code>golden/labelling_protocol.md</code> first. Label independently; do not confer and do not open the other annotator's sheet or <code>candidates_sourcelabels.csv</code>.</p>
<div class="row">I am <select id="who"><option value="A">Annotator A (Gabriel)</option><option value="B">Annotator B (Alvin)</option></select>
<button class="primary" onclick="start()">Start / resume</button></div>
<p id="storewarn" class="warn" style="display:none">This browser is blocking local storage, so progress will NOT autosave. Export before closing the tab.</p></div>
<div class="card" id="main" style="display:none">
<div class="row" style="margin:0"><b id="pos"></b><small id="rowid"></small><span style="flex:1"></span><small id="done"></small></div>
<div class="bar"><div id="prog"></div></div>
<div id="txt"></div>
<div class="row">Confidence: <label><input type="radio" name="c" value="high"> high</label><label><input type="radio" name="c" value="low"> low</label></div>
<div class="row" style="flex-wrap:nowrap">Notes:&nbsp;<input id="notes" style="flex:1;min-width:0" placeholder="rule applied (e.g. &sect;4 precedence), runner-up category, POOR FIT, UNDECIDABLE"></div>
<div class="row"><button onclick="go(-1)">&larr; Prev</button><button onclick="go(1)">Next &rarr;</button><button onclick="nextUnl()">Next unlabelled</button><span style="flex:1"></span><button class="primary" onclick="exportCsv()">Export labels CSV</button></div>
<small>Keys: <b>1&ndash;7</b> label &middot; <b>H</b>/<b>L</b> confidence &middot; <b>&larr; &rarr;</b> move &middot; <b>N</b> next unlabelled</small></div></div>
<div class="card" id="cats" style="align-self:start"></div></div>
<script>
const D=__DATA__, C=__CATS__;
let who, st, i=0, canStore=true;
try{localStorage.setItem('_t','1');localStorage.removeItem('_t')}catch(e){canStore=false;document.getElementById('storewarn').style.display='block'}
const key=()=>"p29_labels_"+who;
function save(){if(canStore)try{localStorage.setItem(key(),JSON.stringify(st))}catch(e){}}
function start(){who=document.getElementById('who').value;
 try{st=canStore?JSON.parse(localStorage.getItem(key())||"null"):null}catch(e){st=null}
 if(!st)st={started:new Date().toISOString(),labels:{}};save();
 document.getElementById('setup').style.display='none';document.getElementById('main').style.display='block';
 const k=D.findIndex(d=>!(st.labels[d.row]||{}).label);i=k<0?0:k;render()}
function cur(){return st.labels[D[i].row]||(st.labels[D[i].row]={})}
function render(){const d=D[i],l=st.labels[d.row]||{},n=D.filter(x=>(st.labels[x.row]||{}).label).length;
 document.getElementById('pos').textContent=`Ticket ${i+1} / ${D.length}`;document.getElementById('rowid').textContent=`row ${d.row}`;
 document.getElementById('txt').textContent=d.narrative;document.getElementById('done').textContent=`${n} of ${D.length} labelled`;
 document.getElementById('prog').style.width=(100*n/D.length)+'%';document.getElementById('notes').value=l.notes||'';
 document.querySelectorAll('input[name=c]').forEach(r=>r.checked=(r.value===l.confidence));
 document.getElementById('cats').innerHTML='<b>Category</b>'+C.map((c,k)=>`<button class="cat ${l.label===c[0]?'sel':''}" onclick="pick(${k})"><span class="k">${k+1}</span>${c[0]}</button><div class="def">${c[1]}</div>`).join('')}
function pick(k){cur().label=C[k][0];save();render()}
function setConf(v){cur().confidence=v;save();render()}
document.addEventListener('change',e=>{if(e.target.name==='c')setConf(e.target.value);if(e.target.id==='notes'){cur().notes=e.target.value;save()}});
function go(s){i=Math.max(0,Math.min(D.length-1,i+s));render()}
function nextUnl(){const k=D.findIndex((d,j)=>j>i&&!(st.labels[d.row]||{}).label);if(k>=0){i=k;render()}}
document.addEventListener('keydown',e=>{if(!st||(e.target.tagName==='INPUT'&&e.target.type!=='radio'))return;
 if(e.key>='1'&&e.key<='7')pick(+e.key-1);else if(e.key==='ArrowRight')go(1);else if(e.key==='ArrowLeft')go(-1);
 else if(e.key==='h'||e.key==='H')setConf('high');else if(e.key==='l'||e.key==='L')setConf('low');else if(e.key==='n'||e.key==='N')nextUnl()});
function q(s){s=String(s??'');return /[",\n\r]/.test(s)?'"'+s.replace(/"/g,'""')+'"':s}
function exportCsv(){const missing=D.filter(d=>!(st.labels[d.row]||{}).label).length;
 if(missing&&!confirm(missing+' ticket(s) still unlabelled. agreement.py will refuse an incomplete sheet. Export anyway?'))return;
 const out='row,label,confidence,notes,narrative\r\n'+D.map(d=>{const l=st.labels[d.row]||{};return [d.row,q(l.label),q(l.confidence),q(l.notes),q(d.narrative)].join(',')}).join('\r\n')+'\r\n';
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([out],{type:'text/csv'}));a.download=`labels_${who}.csv`;a.click()}
</script></body></html>"""


def main() -> int:
    with open(ROOT / "golden" / "candidates.csv", newline="", encoding="utf-8") as fh:
        data = [{"row": r["row"], "narrative": r["narrative"]} for r in csv.DictReader(fh)]
    html = (PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__CATS__", json.dumps(CATS)).replace("__N__", str(len(data))))
    out = ROOT / "golden" / "labeller.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(data)} tickets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
