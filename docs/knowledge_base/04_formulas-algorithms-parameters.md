# 04 — Formulas / Algorithms / Parameters (with file:line)

Source: exhaustive hunt (`manning|runoff|infiltration|DEM|slope|A*|dijkstra|loss|RMSE|threshold|coefficient|rainfall|discharge|depth|velocity`). `IOU`: zero hits. Closest: BCE mask, RMSE, CSI (docstring only), flooded mask ≥0.05. No hallucinated sources; unknown → marked.

## 1. Surface solver — simulation/surface/runoff.py:1-64 (Bates & De Roo 2000 style)

Header: `h[t+1]=h+dt*(R-I)/3600-dt*drain/3600+dt*(Qin-Qout)/A`; `q=(h_flow^(5/3)/n)*sqrt(S)*dx` (Manning, wide-channel R~h).
- Flow depth `:17-18,26-27`: `hf=max(ws1,ws2)-max(z1,z2)`, clip ≥0 [m]. Storage-cell def; kills negatives on DSM steps.
- Slope cap `S_CAP=0.05` `:15,19,28`: `S=min(|Δws|/dx,0.05)` [-]. Comment: 30 m DSM steps are not real channel slopes. √S max ~0.2236.
- Manning flux `:20-23,29-32`: `n=mean(n1,n2) floor 1e-3`; `q=hf^(5/3)/n*sqrt(max(S,1e-8))*dx` [m³/s]; sign by ws drop. Source `source.md:45,89` Sf=n²V²/R^4/3, V=(1/n)R^2/3 S^1/2, Q=A·V (`knowledge.md:160`).
- Walls `:33-38`: any face touching `blocked=(~in_domain)|is_building` (`simulate.py:68`) → 0.
- Stability 1/8-volume `:41-46`: `qmax=0.125*max(h_up,0)*dx²/max(dt,1e-9)`; clip per-face. 0.125×4 faces = max ½ volume. (`knowledge.md:158`.)
- Update `:55-57`: `dh=dt*(rain-infil)/3.6e6-dt*drain+dt*Qin/dx²` [m]; floor 0; `h_min` default 0.0 (config 0.001 exists but not passed `simulate.py:94`).
- Velocity proxy `:58-63`: `|Qin|/max(max(h2,h)*dx,1e-9)` clip [0,3.0] [m/s]. NOT momentum. Dead `vE` branch (`if False`, `knowledge.md:162`).

## 2. Infiltration — simulation/surface/infiltration.py:1-41 (EPA SWMM) — DEAD CLASS

- Horton `:4-5,32-33`: `f(t)=fc+(f0-fc)e^(-kt)`; `f=min(cap,rain)` [mm/h]. Live config `hydraulics.yaml:13-14`: road {5,1,2.0}, open {35,8,2.5}, building {0,0,1.0} (f0,fc,k). BUT live path `simulate.py:63,83` hardcodes `kk=2.2` all classes — config k silently unused (`knowledge.md:182-184`).
- SCS-CN `:20,37-40` (unwired): `Smax=25400/CN-254` [mm]; `F1=P-P²/(P+S)`; `f=(F1-F0)/dt`. CN road 98/open 78/bld 98 (`hydraulics.yaml:16-19`). Floors S 1e-6, +1e-9, dt 1e-9.
- Live inline `simulate.py:60-89`: `cls=road0/open1/bld2` (`:59`); f0/fc per-class, kk=2.2; `dep road 1.0/open 2.5/bld 0.0` [mm] ×dep_scale U(0.5,1.5); depression fills before ponding, never drains (mass sink); `eff=max(rain-f,0)-to_dep` [mm/h].

## 3. Pipes — simulation/hydraulics/pipes.py:1-74 + network.py:10-13

- Capacity `network.py:10-13`: `Qcap=(1/n)A R^2/3 √S`, A=πD²/4, R=D/4, slope floor 1e-4, n=0.013 concrete (Chow 1959). Test `test_simulator.py:23` Q(0.6,0.005,0.013)∈0.2–1.0.
- Diameters [0.3,0.45,0.6,0.8,1.0,1.2] default 0.6 trunk 1.0; S∈[0.002,0.05]; max_len 120; n∈[0.011,0.017]; inlet_cap 0.05 range [0.02,0.10]; nodes rim 0.0 depth 1.5 area 1.0 (`drainage.yaml:8-20`).
- Slope synth `:87-89`: `S=clip((gu-gv)/dist+0.003,min,max)` — +0.003 forces downhill on flat DEM.
- Score `:20-22`: `accum+low*max+clip(12-road_dist,0,12)*(max/12)*0.5`; inlets 60 spacing 15 m; jitter 5 m; outfalls 2 lowest (conf 0.35 vs 0.55/0.45); DAG closer-to-outfall + cost `dist-clamp(dGround,-2,5)*8.0` (`:78-79`).
- Step: `eff_cap=cap*(1-blk)` (`:29`, clip 0.99); `eff_inlet*=(1-0.8*edge_blk)` (`:31-35`); capture `min(eff_inlet,ponded*dx²/dt)` ×0.3 if surcharged (`:38-46`); downhill route (`:48-56`); `node+=inflow*dt/1.0` (`:58`); `surcharge=head>0` (`:60-62`); return `overflow*1.0/dt/dx²` mass-exact (`:64-69`); `sink=capture/dx²` (`:71-73`). Node 1.0 m² ×1.5 m; free outfalls; `surcharge_head 0.0 / weir 1.7` unused.

## 4. Terrain twin — twin.py:11-188 + terrain.yaml

Geo `LAT0/LON0=28.7525/77.49847`, `M_LAT=111320`, `M_LON=111320*cos(lat0)` [m/deg] (`:11-12`). Grid dx 5 nx 160 (~800 m) ny 110 (~550 m). DEM 13×20 coarse 30 m acc 4 m DSM → NaN→cKDTree → zoom order=1 → crop/pad → micro-relief ±0.075 rng26085 (`:95-121`). Masks road_half 4.0; manning 0.015/0.045/0.20/0.05; imperv 1.0/1.0/0.35 (`:123-152`). Hydro: slope=hypot(gradient); D8 steepest `drop=(z-zn)/(dx*hypot)`; accum high→low; low=(acc≥p90)&domain&~bld (`:154-188`).

## 5. Rainfall — generator.py:5-96 + rainfall.yaml

Temporal: uniform 1; peaked `1-|t-0.5|*2*0.85` (min 0.15); front `e^-3t+0.15`; back `e^-3(1-t)+0.15`; multi `0.6+0.4*sin(2π(2+randint(1,3))t+U)²*2`; floor 0.05. Spatial: gradient `0.4+1.2g`; gaussian `0.15+2.2e^(-r²/2s²)`; multi `0.15+Σ1.4e^…×randint(2,4)`; moving `0.1+2.4e^…`, pos=c+v(t-T/2), v from ang/spd. Sigma spec or U(40,150) clip [10,400]; speed U(2,10) train. Normalise `rain/=max(mean,1e-9)*(total/nt)` [mm/step]; `nt=max(2,dur*60/dt)`. Ranges 1–6 h, 10–150 mm, peak 90, step 5 (`rainfall.yaml`).
Coupling `simulate.py:39-47`: wet=twin domain&~bld; force wet-mean=total; `nt=dur*60/dt`; recession zeros appended post-norm (totals exact); substep `sdt=2.0→dt/sub` (`:52-53`, dt_max 5.0/cfl 0.4 unused); flood `hthr=0.05` (`:72,99,105`); TTF first exceed (k+1)*dt/60 [min].

## 6. Scenarios — spec.py:4 + suite_v2.py:28-314

Legacy BLOCKAGE [0,.10,.25,.50,.75,.90]. v1 RAIN trace 3–12 (8%) / light 12–30 (12%) / moderate 30–60 (30%) / heavy 60–100 (30%) / extreme 100–150 (20%). BLOCKAGE_QUOTA [(0,.30),(.10,.20),(.25,.15),(.50,.15),(.75,.10),(.90,.10)]; modes round-robin; N=6. LHS dur 0.5–6 / sigma 40–150 / speed 2–10; drain_eff U(0.7,1.3) (free 1.2–1.35); manning 0.9–1.1; dep 0.5–1.5; imperv 0.25–0.45; jitter σ0.05; recession {0,0,0,0.5,1,1.5,2}; split 70/15/15 stratified (rain_base,blocked_any). Edge 15%: free_drain 90–150/blk0; blocked_moderate 25–60/blk.75/.90; bullseye 30–90 gaussian; rapid 60–120/blk.5/.75 outfall. OOD dur 6–8/total 150–200/sigma 25–40/speed 10–15/drain 0.5–0.65/blk [0.6,0.85]. Topup dry 1–8 mm ids10000+; longdry 3–12/12–25 mm 3.5–6 h ids20000+.
Blockage modes `simulate.py:7-19`: pipe_uniform b=level; inlet_subset n=int(nE*min(level+0.15,1)) b=min(0.95,level+0.2); outfall_restricted outfall min(0.95,level+0.25) else level*0.4 (run.py else *0.6 variant).

## 7. Validation gates — checks.py + simulation.yaml

Surface: finite, ≥-1e-9, max≤2.0 m, vel≤3.0. Mass `err=|rain-(infil+dep+discharged+stored+ponded)|/max(rain,1e-6)` ≤0.35 (config mass_tol 0.05 aspirational; quarantine 0.35 enforced `run_v2.py:105`). Lowpoints mean|low ≥0.8×rest. Graph D∈[0.1,2] S∈[0.0005,0.2] cap>0 no orphans ≥1 outfall.

## 8. ML — baseline_unet / ml_dataset / train

UNet in 36 (9 static+18 hist+9 future) → 9 leads; e1 36→32 e2→64 e3→128 pool up/d Conv1×1 32→9; 476,297 params. Loss `MSE(pred,y)+0.2*BCE(pred,(y≥0.05))`; Adam 1e-3 batch 4/16 epochs 5/10; val RMSE per-lead sqrt(mean((pv-yv)²)); reported +30 0.048/+180 0.049. Windows LEADS [1,2,4,6,8,12,18,24,36]×5=5..180 HIST 6; static [dem,slope,log1p(accum),low,imperv,manning,road,bld,domain]; TTF (first+1)*5 NaN never; norm (x-mean)/std; NaN→-1 torch. Welford streaming, stride 20000, train-only.

## 9. Routing + viz thresholds

A* `route.py`: ok=valid&(depth<0.05); costs 5.0/7.07; heur Manhattan×5; heapq. Nowcast `flooded_m2=count(≥0.05)*25` (25=5×5). Planner `flood_planner.html:88-90,149-166`: bands <0.05 CLEAR/<0.15 WATCH/<0.30 WARNING/else DANGER; edgeDepth max 5 samples; ≥0.30 skip; weight w*(safe?1+10*min(d,0.30)/0.30:1); onset first lead ≥0.05. Viz `export_viz.py:13-14,94-106,134`: NODE_MAXDEPTH 1.5, FLOOD 0.05, cells=count(depth_q≥50&dom), m2×25, quant dem cm/rain dmm/depth mm/vel cm clip[0,3]/pipe×1e5/TTF -1 never. Stats severity <0.05/<0.15/<0.40/else severe; QC severe≥0.4/minor≥0.05 vmin0 vmax0.5.

## 10. Magic numbers master list

0.05 flood/slope-cap/jitter/mass-tol; 0.15/0.30/0.40 bands; 5.0 dx/orth, 7.07 diag, 25 area; 2.0 substep/depth-cap, 3.0 vel-cap/Horton shape, 1.5 node depth, 1.0 node area/dep-road, 2.5 dep-open/Horton-k; 2.2 hardcoded kk; 0.125 limiter; 0.3 surcharge; 0.8 blk→inlet; 0.99/0.95 clips; +0.15/+0.2/+0.25 bumps; 1e-3 n-floor, 1e-4 pipe-S, 1e-8 sqrt, 1e-6 S/mass, 1e-9 dt/div, -1e-9 neg-tol; 25400/254 SCS; CN 0/98/78; weir 1.7 unused; pipe n 0.013 (0.011–0.017); land n 0.015/0.045/0.20/0.05; geo 111320, 28.7525/77.49847/28.7523; +0.003 nudge; pipe S [0.002,0.05]; 120 m max; 60 inlets; 15 m spacing; 12 m road bonus; 5 m jitter; p90 low; 0.35 quarantine; 0.4 CFL unused; 0.001 h_min unused; 0.2 BCE; 1e-3 lr; 36 ch; 476297 params; 2692/542/606/1861 windows.
