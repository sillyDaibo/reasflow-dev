"""Data preparation and evaluation helpers for the four paper experiments."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
from scipy.special import expit
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from strat_models import cartesian_product, from_networkx, product_grid, set_edge_weight
from strat_models.solvers import (
    bernoulli_prox,
    fit_admm,
    logistic_local_prox,
    poisson_prox,
    ridge_prox,
    ridge_regularizer_prox,
)


ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(os.environ.get("STRAT_MODELS_ASSETS", "/home/hzy/optirepro/datasets/reproduction/v1/assets"))


def _fit_result_dir(experiment_id: str) -> Path:
    path = ROOT / "results" / "formal" / experiment_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _json_safe(value):
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def write_metrics(path: Path, metrics: dict) -> None:
    path.write_text(json.dumps(metrics, indent=2, sort_keys=True, default=_json_safe) + "\n", encoding="utf-8")


def make_result_metadata(result_dir: Path, config: dict, metrics: dict, source: dict) -> None:
    write_metrics(result_dir / "metrics.json", metrics)
    write_metrics(result_dir / "resolved_config.json", config)
    write_metrics(result_dir / "data_provenance.json", source)


def _node_index(nodes):
    return {node: i for i, node in enumerate(nodes)}


def _fit_ridge(X, y, z, graph, *, ridge=0.0, intercept=True, maxiter=250, tol=1e-5, cg=50, verbose=False):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float).reshape(-1, 1)
    if intercept:
        X = np.column_stack((X, np.ones(len(X))))
        intercept_index = X.shape[1] - 1
    else:
        intercept_index = None
    p = X.shape[1]
    index = _node_index(graph.nodes)
    xtx = np.zeros((len(graph.nodes), p, p), dtype=float)
    xty = np.zeros((len(graph.nodes), p, 1), dtype=float)
    for row, target, node in zip(X, y, z):
        i = index[node]
        xtx[i] += np.outer(row, row)
        xty[i, :, 0] += row * target[0]

    def loss_prox(t, nu, warm):
        return ridge_prox(t, nu, warm, (xtx, xty))

    def reg_prox(t, nu, warm):
        return ridge_regularizer_prox(t, nu, warm, ridge, intercept_index)

    params, state, info = fit_admm(graph, (p, 1), loss_prox, reg_prox, maxiter=maxiter,
                                   abs_tol=tol, rel_tol=tol, max_cg_iterations=cg, verbose=verbose)
    return params[:, :, 0], info


def _ridge_predict(params, X, z, nodes, intercept=True):
    X = np.asarray(X, dtype=float)
    if intercept:
        X = np.column_stack((X, np.ones(len(X))))
    index = _node_index(nodes)
    coef = np.asarray([params[index[node]] for node in z])
    return np.sum(X * coef, axis=1)


def run_mesothelioma(seed=0, maxiter=120, verbose=False):
    import matplotlib.pyplot as plt

    result_dir = _fit_result_dir("exp_001_mesothelioma")
    archive = ASSETS / "mesothelioma_uci" / "mesothelioma.zip"
    extract_dir = ROOT / ".run-data" / "mesothelioma"
    extract_dir.mkdir(parents=True, exist_ok=True)
    xlsx = extract_dir / "Mesothelioma data set.xlsx"
    if not xlsx.exists():
        with zipfile.ZipFile(archive) as zf:
            zf.extract("Mesothelioma data set.xlsx", extract_dir)
    df = pd.read_excel(xlsx)
    target = (df["class of diagnosis"].astype(int) - 1).to_numpy()
    ages = df["age"].astype(int).to_numpy()
    sexes = np.where(df["gender"].to_numpy() == 1, "Male", "Female")
    # This is the paper's 46-dimensional feature engineering: preserve age and
    # gender, one-hot four categorical fields, and remove diagnosis leakage.
    features = df.drop(columns=["age", "gender", "class of diagnosis", "diagnosis method"])
    features = pd.get_dummies(features, columns=["city", "keep side", "type of MM", "habit of cigarette"], dtype=float)
    X = features.to_numpy(dtype=float)
    z = [(str(s), int(a)) for s, a in zip(sexes, ages)]
    idx_train, idx_test = train_test_split(np.arange(len(df)), test_size=0.1, random_state=seed)
    scaler = StandardScaler().fit(X[idx_train])
    X_train, X_test = scaler.transform(X[idx_train]), scaler.transform(X[idx_test])
    y_train, y_test = target[idx_train], target[idx_test]
    z_train, z_test = [z[i] for i in idx_train], [z[i] for i in idx_test]
    sex_graph = nx.Graph(); sex_graph.add_nodes_from(["Male", "Female"]); sex_graph.add_edge("Male", "Female", weight=10.0)
    age_graph = nx.path_graph(np.arange(19, 86)); set_edge_weight(age_graph, 500.0)
    graph = from_networkx(cartesian_product([sex_graph, age_graph]))
    index = _node_index(graph.nodes)
    p = X_train.shape[1] + 1
    Xn = np.column_stack((X_train, np.ones(len(X_train))))
    by_x, by_y = [None] * len(graph.nodes), [None] * len(graph.nodes)
    for node in graph.nodes:
        by_x[index[node]] = []
        by_y[index[node]] = []
    for row, yy, node in zip(Xn, y_train, z_train):
        by_x[index[node]].append(row); by_y[index[node]].append(yy)
    by_x = [np.asarray(v) if v else None for v in by_x]; by_y = [np.asarray(v, dtype=float) for v in by_y]
    def lprox(t, nu, warm):
        return logistic_local_prox(t, nu, warm, by_x, by_y)
    def rprox(t, nu, warm):
        return ridge_regularizer_prox(t, nu, warm, 0.1, p - 1)
    params, _, info = fit_admm(graph, (p,), lprox, rprox, maxiter=maxiter, abs_tol=1e-4, rel_tol=1e-4,
                               max_cg_iterations=40, verbose=verbose)
    def scores(Xv, zv):
        mat = np.column_stack((Xv, np.ones(len(Xv))))
        return np.asarray([mat[i] @ params[index[node]] for i, node in enumerate(zv)])
    logits_train, logits_test = scores(X_train, z_train), scores(X_test, z_test)
    strat_metrics = {
        "anll_train": float(np.mean(np.logaddexp(0, logits_train) - y_train * logits_train)),
        "anll_test": float(np.mean(np.logaddexp(0, logits_test) - y_test * logits_test)),
        "error_test": float(np.mean((expit(logits_test) >= 0.5) != y_test)),
        "parameter_count": int(params.size), "iterations": info.iterations,
    }
    # Separate logistic models are the zero-edge baseline; common is one node.
    for _, _, d in sex_graph.edges(data=True): d["weight"] = 0.0
    set_edge_weight(age_graph, 0.0)
    sep_graph = from_networkx(cartesian_product([sex_graph, age_graph]))
    sep_params, sep_info = _fit_logistic(X_train, y_train, z_train, sep_graph, 0.1, maxiter)
    common_graph = from_networkx(nx.empty_graph(1))
    common_params, common_info = _fit_logistic(X_train, y_train, [0] * len(y_train), common_graph, 0.1, maxiter)
    def eval_logistic(par, nodes, Xv, yv, zv):
        mat = np.column_stack((Xv, np.ones(len(Xv))))
        ll = []
        for row, yy, node in zip(mat, yv, zv):
            val = row @ par[_node_index(nodes)[node]]
            ll.append(np.logaddexp(0, val) - yy * val)
        return float(np.mean(ll)), float(np.mean((np.asarray(ll) * 0 + (expit(np.asarray([row @ par[_node_index(nodes)[node]] for row, node in zip(mat, zv)])) >= .5)) != yv))
    sep_anll, sep_err = eval_logistic(sep_params, sep_graph.nodes, X_test, y_test, z_test)
    common_anll, common_err = eval_logistic(common_params, common_graph.nodes, X_test, y_test, [0] * len(y_test))
    metrics = {"dataset": "UCI Mesothelioma", "feature_dimension": int(X.shape[1] + 1), "train_records": len(y_train), "test_records": len(y_test),
               "stratified": strat_metrics, "separate": {"anll_test": sep_anll, "error_test": sep_err, "iterations": sep_info.iterations},
               "common": {"anll_test": common_anll, "error_test": common_err, "iterations": common_info.iterations},
               "paper_reference": {"stratified_anll": 0.76, "stratified_error": 0.27}}
    config = {"seed": seed, "gamma_local": 0.1, "gamma_sex": 10.0, "gamma_age": 500.0, "maxiter": maxiter, "split": "90/10 random_state=0", "solver": "ADMM"}
    source = {"archive": str(archive), "format": "Mesothelioma data set.xlsx", "records": 324, "sha256": "see shared download_manifest.json"}
    write_metrics(result_dir / "metrics.json", metrics); write_metrics(result_dir / "resolved_config.json", config); write_metrics(result_dir / "data_provenance.json", source)
    plt.figure(figsize=(6, 4))
    for sex, color in [("Male", "tab:blue"), ("Female", "tab:orange")]:
        vals = [params[index[(sex, age)], features.columns.get_loc("glucose") if "glucose" in features.columns else 0] for age in range(19, 86)]
        plt.plot(range(19, 86), vals, label=sex, color=color)
    plt.xlabel("Age"); plt.ylabel("glucose coefficient"); plt.legend(); plt.tight_layout(); plt.savefig(result_dir / "figure_glucose.png", dpi=140); plt.close()
    return metrics


def _fit_logistic(X, y, z, graph, ridge, maxiter):
    index = _node_index(graph.nodes); p = X.shape[1] + 1
    mat = np.column_stack((X, np.ones(len(X))))
    by_x, by_y = [[] for _ in graph.nodes], [[] for _ in graph.nodes]
    for row, yy, node in zip(mat, y, z): by_x[index[node]].append(row); by_y[index[node]].append(yy)
    by_x = [np.asarray(v) if v else None for v in by_x]; by_y = [np.asarray(v, dtype=float) for v in by_y]
    params, _, info = fit_admm(graph, (p,), lambda t, nu, warm: logistic_local_prox(t, nu, warm, by_x, by_y),
                               lambda t, nu, warm: ridge_regularizer_prox(t, nu, warm, ridge, p - 1),
                               maxiter=maxiter, abs_tol=1e-4, rel_tol=1e-4, max_cg_iterations=40)
    return params, info


def run_houses(seed=0, maxiter=180, verbose=False):
    import matplotlib.pyplot as plt
    from sklearn.ensemble import RandomForestRegressor

    result_dir = _fit_result_dir("exp_002_houses")
    archive = ASSETS / "king_county_house_sales" / "kingcounty.zip"
    extract_dir = ROOT / ".run-data" / "houses"; extract_dir.mkdir(parents=True, exist_ok=True)
    csv_path = extract_dir / "kc_house_data.csv"
    if not csv_path.exists():
        with zipfile.ZipFile(archive) as zf: zf.extract("kingcounty/kc_house_data.csv", extract_dir)
        os.replace(extract_dir / "kingcounty" / "kc_house_data.csv", csv_path)
    df = pd.read_csv(csv_path)
    df = df[df["long"] <= -121.6].copy()
    df["log_price"] = np.log(df["price"])
    bins = 50
    df["lat_bin"] = pd.cut(df["lat"], bins=bins, labels=False)
    df["long_bin"] = pd.cut(df["long"], bins=bins, labels=False)
    df = df.dropna(subset=["lat_bin", "long_bin"])
    feature_names = ["bedrooms", "bathrooms", "sqft_living", "sqft_lot", "floors", "waterfront", "condition", "grade", "yr_built"]
    idx_train, idx_test = train_test_split(np.arange(len(df)), test_size=0.25, random_state=seed)
    X = df[feature_names].to_numpy(float); y = df["log_price"].to_numpy(float); z = list(zip(df["lat_bin"].astype(int), df["long_bin"].astype(int)))
    scaler = StandardScaler().fit(X[idx_train]); Xtr, Xte = scaler.transform(X[idx_train]), scaler.transform(X[idx_test])
    graph_nx = nx.grid_2d_graph(bins, bins); set_edge_weight(graph_nx, 15.0); graph = from_networkx(graph_nx)
    params, info = _fit_ridge(Xtr, y[idx_train], [z[i] for i in idx_train], graph, ridge=1.0, intercept=True, maxiter=maxiter, tol=1e-5, cg=40, verbose=verbose)
    pred_tr = _ridge_predict(params, Xtr, [z[i] for i in idx_train], graph.nodes); pred_te = _ridge_predict(params, Xte, [z[i] for i in idx_test], graph.nodes)
    def rmse(a, b): return float(np.sqrt(np.mean((a - b) ** 2)))
    # Separate and common fits use the same standardized features and local ridge.
    sep_graph_nx = nx.grid_2d_graph(bins, bins); set_edge_weight(sep_graph_nx, 0.0); sep_graph = from_networkx(sep_graph_nx)
    sep_params, sep_info = _fit_ridge(Xtr, y[idx_train], [z[i] for i in idx_train], sep_graph, ridge=1.0, intercept=True, maxiter=maxiter, tol=1e-5, cg=20)
    common_graph = from_networkx(nx.empty_graph(1)); common_params, common_info = _fit_ridge(Xtr, y[idx_train], [0] * len(idx_train), common_graph, ridge=1.0, intercept=True, maxiter=maxiter, tol=1e-5, cg=20)
    sep_pred = _ridge_predict(sep_params, Xte, [z[i] for i in idx_test], sep_graph.nodes); common_pred = _ridge_predict(common_params, Xte, [0] * len(idx_test), common_graph.nodes)
    rf_features = feature_names + ["lat", "long"]
    rf = RandomForestRegressor(n_estimators=50, random_state=seed, n_jobs=-1, min_samples_leaf=1)
    rf.fit(df.iloc[idx_train][rf_features], y[idx_train]); rf_pred = rf.predict(df.iloc[idx_test][rf_features])
    metrics = {"dataset": "King County house sales", "train_records": len(idx_train), "test_records": len(idx_test), "bins": [bins, bins],
               "stratified": {"rmse_train": rmse(pred_tr, y[idx_train]), "rmse_test": rmse(pred_te, y[idx_test]), "parameter_count": int(params.size), "iterations": info.iterations},
               "separate": {"rmse_test": rmse(sep_pred, y[idx_test]), "parameter_count": int(sep_params.size), "iterations": sep_info.iterations},
               "common": {"rmse_test": rmse(common_pred, y[idx_test]), "parameter_count": int(common_params.size), "iterations": common_info.iterations},
               "random_forest": {"rmse_test": rmse(rf_pred, y[idx_test]), "parameter_count": int(sum(e.tree_.node_count for e in rf.estimators_)), "trees": 50},
               "paper_reference": {"stratified_rmse": 0.181, "random_forest_rmse": 0.184}}
    config = {"seed": seed, "gamma_local": 1.0, "gamma_geo": 15.0, "maxiter": maxiter, "bins": 50, "split": "75/25 random_state=0", "solver": "ADMM"}
    source = {"archive": str(archive), "file": "kingcounty/kc_house_data.csv", "filter": "long <= -121.6"}
    write_metrics(result_dir / "metrics.json", metrics); write_metrics(result_dir / "resolved_config.json", config); write_metrics(result_dir / "data_provenance.json", source)
    plt.figure(figsize=(5, 4)); plt.imshow(params[:, -1].reshape(bins, bins), cmap="coolwarm"); plt.colorbar(label="intercept"); plt.title("Stratified house-price intercept"); plt.tight_layout(); plt.savefig(result_dir / "figure_coefficients.png", dpi=140); plt.close()
    return metrics


STATE_NEIGHBORS = """AL:FL,GA,MS,TN;AK:WA;AZ:CA,CO,NM,NV,UT;AR:LA,MO,MS,OK,TN,TX;CA:AZ,NV,OR;CO:AZ,KS,NE,NM,OK,UT,WY;CT:MA,NY,RI;DE:MD,NJ,PA;FL:AL,GA;GA:AL,FL,NC,SC,TN;HI:CA;ID:MT,NV,OR,UT,WA,WY;IL:IA,IN,KY,MO;IN:IL,KY,MI,OH;IA:IL,MN,MO,NE,SD,WI;KS:CO,MO,NE,OK;KY:IL,IN,MO,OH,TN,VA,WV;LA:AR,MS,TX;ME:NH;MD:DE,PA,VA,WV;MA:CT,NH,NY,RI,VT;MI:IN,OH,WI;MN:IA,ND,SD,WI;MS:AL,AR,LA,TN;MO:AR,IA,IL,KS,KY,NE,OK,TN;MT:ID,ND,SD,WY;NE:CO,IA,KS,MO,SD,WY;NV:AZ,CA,ID,OR,UT;NH:MA,ME,VT;NJ:DE,NY,PA;NM:AZ,CO,OK,TX,UT;NY:CT,MA,NJ,PA,VT;NC:GA,SC,TN,VA;ND:MN,MT,SD;OH:IN,KY,MI,PA,WV;OK:AR,CO,KS,MO,NM,TX;OR:CA,ID,NV,WA;PA:DE,MD,NJ,NY,OH,WV;RI:CT,MA;SC:GA,NC;SD:IA,MN,MT,ND,NE,WY;TN:AL,AR,GA,KY,MS,MO,NC,VA;TX:AR,LA,NM,OK;UT:AZ,CO,ID,NM,NV,WY;VT:MA,NH,NY;VA:KY,MD,NC,TN,WV;WA:ID,OR;WV:KY,MD,OH,PA,VA;WI:IA,IL,MI,MN;WY:CO,ID,MT,NE,SD,UT"""


def state_graph(weight):
    graph = nx.Graph(); states = sorted({part.split(":")[0] for part in STATE_NEIGHBORS.split(";")}); graph.add_nodes_from(states)
    for item in STATE_NEIGHBORS.split(";"):
        state, neighbors = item.split(":")
        for other in neighbors.split(","): graph.add_edge(state, other, weight=float(weight))
    return graph


def run_senate(seed=0, maxiter=180, verbose=False):
    import matplotlib.pyplot as plt
    result_dir = _fit_result_dir("exp_003_senate")
    path = ASSETS / "us_senate_1976_2016" / "1976-2024-senate-state.tab"
    df = pd.read_csv(path, sep=",")
    df = df[(df.year >= 1976) & (df.year <= 2016) & (df.stage == "gen")].copy()
    df["democrat"] = (df["party_simplified"].str.upper() == "DEMOCRAT").astype(float)
    winners = df.loc[df.groupby(["year", "state_po"])["candidatevotes"].idxmax(), ["year", "state_po", "democrat"]]
    states = sorted(state_graph(1).nodes); years = list(range(1976, 2017, 2)); index_data = {(s, y): float(r.democrat) for r in winners.itertuples(index=False) for s, y in [(r.state_po, int(r.year))]}
    train = [(s, y, val) for (s, y), val in index_data.items() if y <= 2012]; test = [(s, y, val) for (s, y), val in index_data.items() if y >= 2014]
    nodes = [(s, y) for s in states for y in years]; graph_state = state_graph(1); graph_year = nx.path_graph(years); set_edge_weight(graph_year, 4.0); graph = from_networkx(cartesian_product([graph_state, graph_year]))
    index = _node_index(graph.nodes); counts = np.zeros((len(nodes), 2));
    for s, y, val in train: counts[index[(s, y)], 0] += 1; counts[index[(s, y)], 1] += val
    def lprox(t, nu, warm): return bernoulli_prox(t, nu, warm, counts)
    params, _, info = fit_admm(graph, (1,), lprox, lambda t, nu, warm: nu, maxiter=maxiter, abs_tol=1e-5, rel_tol=1e-5, max_cg_iterations=50, verbose=verbose)
    p = np.clip(params[:, 0], 1e-5, 1 - 1e-5)
    def anll(records, pp): return float(np.mean([-np.log(pp[index[(s, y)]]) if val else -np.log(1 - pp[index[(s, y)]]) for s, y, val in records]))
    # Separate model and common Bernoulli baselines.
    sep_graph_state = state_graph(0); sep_graph_year = nx.path_graph(years); set_edge_weight(sep_graph_year, 0); sep = from_networkx(cartesian_product([sep_graph_state, sep_graph_year])); sep_idx = _node_index(sep.nodes); sep_p = np.array([(counts[ index[node], 1] / counts[index[node], 0]) if counts[index[node], 0] else 0.5 for node in sep.nodes]); sep_p = np.clip(sep_p, 1e-5, 1 - 1e-5)
    common_p = np.array([counts[:, 1].sum() / max(counts[:, 0].sum(), 1)]); common_p = np.clip(common_p, 1e-5, 1 - 1e-5)
    sep_anll_test = float(np.mean([-np.log(sep_p[sep_idx[(s, y)]]) if val else -np.log(1 - sep_p[sep_idx[(s, y)]]) for s, y, val in test]))
    common_anll_test = float(np.mean([-np.log(common_p[0]) if val else -np.log(1 - common_p[0]) for _, _, val in test]))
    metrics = {"dataset": "U.S. Senate elections", "train_records": len(train), "test_records": len(test), "nodes": len(nodes),
               "stratified": {"anll_train": anll(train, p), "anll_test": anll(test, p), "iterations": info.iterations, "parameter_count": int(params.size)},
               "separate": {"anll_train": float(np.mean([-np.log(sep_p[sep_idx[(s, y)]]) if val else -np.log(1-sep_p[sep_idx[(s, y)]]) for s, y, val in train])), "anll_test": sep_anll_test},
               "common": {"anll_train": float(np.mean([-np.log(common_p[0]) if val else -np.log(1-common_p[0]) for _, _, val in train])), "anll_test": common_anll_test},
               "paper_reference": {"stratified_test_anll": 0.61, "common_test_anll": 0.70}}
    config = {"seed": seed, "gamma_state": 1.0, "gamma_year": 4.0, "epsilon": 1e-5, "maxiter": maxiter, "solver": "ADMM"}
    source = {"file": str(path), "years": "1976-2016", "adjacency": "embedded Census state-border list (109 undirected edges); AK-WA and HI-CA links preserve connectivity"}
    write_metrics(result_dir / "metrics.json", metrics); write_metrics(result_dir / "resolved_config.json", config); write_metrics(result_dir / "data_provenance.json", source)
    heat = np.array([[p[index[(s, y)]] for y in years] for s in states]); plt.figure(figsize=(10, 8)); plt.imshow(heat, aspect="auto", cmap="coolwarm", vmin=0, vmax=1); plt.yticks(range(len(states)), states); plt.xticks(range(len(years)), years, rotation=90); plt.colorbar(label="P(Democrat)"); plt.tight_layout(); plt.savefig(result_dir / "figure_heatmap.png", dpi=140); plt.close()
    return metrics


def run_chicago(seed=0, maxiter=80, verbose=False):
    import matplotlib.pyplot as plt
    result_dir = _fit_result_dir("exp_004_chicago")
    path = ASSETS / "chicago_crimes_2017_2018" / "chicago_crimes_2017_2018.parquet"
    df = pd.read_parquet(path)
    df = df[df["year"].isin([2017, 2018])].copy()
    df = df[df["Longitude"] > -87.85].dropna(subset=["Latitude", "Longitude"])
    bins = 20
    df["lat_bin"] = pd.cut(df["Latitude"], bins=bins, labels=False)
    df["lon_bin"] = pd.cut(df["Longitude"], bins=bins, labels=False)
    dates = pd.to_datetime(df["Date"])
    df["week"] = ((dates.dt.isocalendar().week.astype(int) - 1) % 52).astype(int)
    df["day"] = dates.dt.dayofweek.astype(int); df["hour_bin"] = dates.dt.hour.astype(int)
    df = df.dropna(subset=["lat_bin", "lon_bin"]); df["lat_bin"] = df["lat_bin"].astype(int); df["lon_bin"] = df["lon_bin"].astype(int)
    shape = (bins, bins, 52, 7, 24); total_nodes = int(np.prod(shape)); counts_train = np.zeros(shape, dtype=float); counts_test = np.zeros(shape, dtype=float)
    for year, target in [(2017, counts_train), (2018, counts_test)]:
        sub = df[df["year"] == year]; ix = (sub["lat_bin"].to_numpy(), sub["lon_bin"].to_numpy(), sub["week"].to_numpy(), sub["day"].to_numpy(), sub["hour_bin"].to_numpy()); np.add.at(target, ix, 1)
    graph = product_grid(shape, [100.0, 100.0, 100.0, 100.0, 100.0], [False, False, True, True, True])
    counts = np.column_stack((np.ones(total_nodes), counts_train.ravel()))
    def lprox(t, nu, warm): return poisson_prox(t, nu, warm, counts)
    params, _, info = fit_admm(graph, (1,), lprox, lambda t, nu, warm: nu, maxiter=maxiter, abs_tol=1e-6, rel_tol=1e-6, max_cg_iterations=25, verbose=verbose)
    rates = np.maximum(params[:, 0].reshape(shape), 1e-5)
    def poisson_anll(y, rate):
        # Include the factorial term, matching scipy.stats.poisson.logpmf.
        from scipy.special import gammaln
        return float(np.mean(rate - y * np.log(rate) + gammaln(y + 1)))
    common_rate = np.full(shape, counts_train.mean()); separate_rate = np.maximum(counts_train, 1e-5)
    metrics = {"dataset": "Chicago crimes", "train_records": int((df.year == 2017).sum()), "test_records": int((df.year == 2018).sum()), "nodes": total_nodes, "grid_shape": list(shape),
               "stratified": {"anll_train": poisson_anll(counts_train, rates), "anll_test": poisson_anll(counts_test, rates), "iterations": info.iterations, "parameter_count": int(params.size)},
               "separate": {"anll_train": poisson_anll(counts_train, separate_rate), "anll_test": poisson_anll(counts_test, separate_rate)},
               "common": {"anll_train": poisson_anll(counts_train, common_rate), "anll_test": poisson_anll(counts_test, common_rate)},
               "paper_reference": {"stratified_test_anll": 0.234, "common_test_anll": 0.278}}
    config = {"seed": seed, "gamma_location": 100.0, "gamma_week": 100.0, "gamma_day": 100.0, "gamma_hour": 100.0, "epsilon": 1e-5, "maxiter": maxiter, "solver": "ADMM", "week_definition": "ISO week modulo 52"}
    source = {"file": str(path), "records": 538425, "split": "2017 train / 2018 test", "preprocessing": "20x20 bins, all 52x7x24 zero-count cells retained"}
    write_metrics(result_dir / "metrics.json", metrics); write_metrics(result_dir / "resolved_config.json", config); write_metrics(result_dir / "data_provenance.json", source)
    loc = rates.mean(axis=(2, 3, 4)); week = rates.mean(axis=(0, 1, 3, 4)); hour = rates.mean(axis=(0, 1, 2, 3))
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.5)); im = ax[0].imshow(loc[::-1]); fig.colorbar(im, ax=ax[0]); ax[0].set_title("location"); ax[1].plot(week); ax[1].set_title("week"); ax[2].plot(hour); ax[2].set_title("hour"); fig.tight_layout(); fig.savefig(result_dir / "figure_rates.png", dpi=140); plt.close(fig)
    return metrics
