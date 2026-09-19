import json, os

# Reference the datasource by NAME (no dropdown variable). Grafana migrates a
# string datasource reference to the matching UID on load.
DS = "victoria-metrics"
_id = [0]
def nid():
    _id[0] += 1
    return _id[0]

GREEN = [{"color": "green", "value": None}]
GOODBAD = [{"color": "red", "value": None}, {"color": "green", "value": 1}]
REDPOS = [{"color": "green", "value": None}, {"color": "red", "value": 1}]
PCT = [{"color": "green", "value": None}, {"color": "yellow", "value": 70}, {"color": "red", "value": 90}]

def _targets(exprs):
    out = []
    for i, e in enumerate(exprs):
        expr, legend = e if isinstance(e, tuple) else (e, "")
        out.append({"datasource": DS, "expr": expr, "legendFormat": legend,
                    "refId": chr(65 + i), "range": True, "instant": False})
    return out

def STAT(title, expr, unit="none", decimals=None, thresholds=None, bg=False, textmode="auto", legend=""):
    def make(x, y, w, h):
        fc = {"defaults": {"unit": unit, "mappings": []}, "overrides": []}
        if decimals is not None: fc["defaults"]["decimals"] = decimals
        if thresholds:
            fc["defaults"]["thresholds"] = {"mode": "absolute", "steps": thresholds}
            fc["defaults"]["color"] = {"mode": "thresholds"}
        else:
            fc["defaults"]["color"] = {"mode": "fixed", "fixedColor": "text"}
        ts = _targets([(expr, legend)])
        for t in ts: t["instant"] = True; t["range"] = False
        return {"type": "stat", "title": title, "datasource": DS, "id": nid(),
                "gridPos": {"h": h, "w": w, "x": x, "y": y}, "fieldConfig": fc,
                "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                            "orientation": "auto", "colorMode": "background" if bg else "value",
                            "graphMode": "area", "justifyMode": "auto", "textMode": textmode},
                "targets": ts}
    return make

def TS(title, exprs, unit="short", stack=False, fill=10, table_legend=False, decimals=None,
       minv=None, maxv=None, desc="", neg_y=None):
    def make(x, y, w, h):
        draw = {"drawStyle": "line", "lineWidth": 1, "fillOpacity": fill, "showPoints": "never", "spanNulls": True}
        if stack: draw["stacking"] = {"mode": "normal", "group": "A"}
        d = {"unit": unit, "custom": draw, "color": {"mode": "palette-classic"}, "mappings": []}
        if decimals is not None: d["decimals"] = decimals
        if minv is not None: d["min"] = minv
        if maxv is not None: d["max"] = maxv
        overrides = []
        leg = {"displayMode": "table" if table_legend else "list", "placement": "bottom",
               "calcs": ["lastNotNull", "max"] if table_legend else []}
        return {"type": "timeseries", "title": title, "datasource": DS, "id": nid(), "description": desc,
                "gridPos": {"h": h, "w": w, "x": x, "y": y},
                "fieldConfig": {"defaults": d, "overrides": overrides},
                "options": {"legend": leg, "tooltip": {"mode": "multi", "sort": "desc"}},
                "targets": _targets(exprs)}
    return make

def TABLE(title, expr, unit="short", desc="", sortdesc=True):
    def make(x, y, w, h):
        t = _targets([(expr, "")])[0]; t["instant"] = True; t["range"] = False; t["format"] = "table"
        return {"type": "table", "title": title, "datasource": DS, "id": nid(), "description": desc,
                "gridPos": {"h": h, "w": w, "x": x, "y": y},
                "fieldConfig": {"defaults": {"unit": unit, "custom": {"align": "auto", "filterable": True}}, "overrides": []},
                "options": {"showHeader": True, "sortBy": [{"displayName": "value", "desc": sortdesc}]},
                "transformations": [{"id": "organize", "options": {
                    "excludeByName": {"Time": True, "__name__": True, "job": True, "service": True},
                    "renameByName": {"Value": "value"}}}],
                "targets": [t]}
    return make

def GAUGE(title, expr, unit="percent", maxv=100, thresholds=None, legend=""):
    th = thresholds or PCT
    def make(x, y, w, h):
        ts = _targets([(expr, legend)])
        return {"type": "gauge", "title": title, "datasource": DS, "id": nid(),
                "gridPos": {"h": h, "w": w, "x": x, "y": y},
                "fieldConfig": {"defaults": {"unit": unit, "min": 0, "max": maxv,
                                "thresholds": {"mode": "absolute", "steps": th}, "color": {"mode": "thresholds"}}, "overrides": []},
                "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                            "showThresholdLabels": False, "showThresholdMarkers": True},
                "targets": ts}
    return make

def TEXT(title, md):
    def make(x, y, w, h):
        return {"type": "text", "title": title, "id": nid(), "gridPos": {"h": h, "w": w, "x": x, "y": y},
                "options": {"mode": "markdown", "content": md}}
    return make

class Board:
    def __init__(self, title, uid, tags, variables):
        self.title = title; self.uid = uid; self.tags = tags; self.variables = variables
        self.panels = []; self.y = 0
    def row(self, title):
        self.panels.append({"type": "row", "title": title, "collapsed": False,
                            "gridPos": {"h": 1, "w": 24, "x": 0, "y": self.y}, "id": nid(), "panels": []})
        self.y += 1
    def add(self, items):
        x = 0; maxh = 0
        for make, w, h in items:
            if x + w > 24:
                x = 0; self.y += maxh; maxh = 0
            self.panels.append(make(x, self.y, w, h)); x += w; maxh = max(maxh, h)
        self.y += maxh
    def to_dict(self):
        return {"title": self.title, "uid": self.uid, "tags": self.tags, "timezone": "browser",
                "schemaVersion": 39, "version": 1, "editable": True, "graphTooltip": 1,
                "refresh": "30s", "time": {"from": "now-6h", "to": "now"},
                "templating": {"list": self.variables},
                "links": [{"type": "dashboards", "tags": ["talos"], "title": "Talos boards",
                           "asDropdown": True, "includeVars": True, "keepTime": True,
                           "targetBlank": False, "icon": "external link"}],
                "annotations": {"list": [{"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                                          "enable": True, "hide": True, "name": "Annotations & Alerts", "type": "dashboard"}]},
                "panels": self.panels}

def var_ds():
    return {"name": "datasource", "type": "datasource", "label": "Data source",
            "query": DS_TYPE, "hide": 0, "refresh": 1, "regex": "",
            "current": {"text": "victoria-metrics", "value": DS_UID}}
def var_query(name, label, q):
    return {"name": name, "type": "query", "label": label, "datasource": DS,
            "query": {"query": q, "refId": name}, "definition": q,
            "includeAll": True, "multi": True, "allValue": ".*",
            "current": {"text": "All", "value": "$__all"}, "refresh": 2, "sort": 1}

NODE = var_query("node", "Node", "label_values(node_memory_MemTotal_bytes, instance)")
NS = var_query("namespace", "Namespace", "label_values(kube_pod_info, namespace)")

boards = []

# ============================= MASTER =============================
b = Board("Talos — Master Overview", "talos-master", ["talos", "overview"], [])
b.row("Fleet health")
b.add([
    (STAT("Nodes Ready", 'sum(kube_node_status_condition{condition="Ready",status="true"})', thresholds=GREEN), 3, 4),
    (STAT("Nodes", "count(kube_node_info)"), 3, 4),
    (STAT("Pods Running", 'sum(kube_pod_status_phase{phase="Running"})', thresholds=GREEN), 3, 4),
    (STAT("Pods Pending/Failed", 'sum(kube_pod_status_phase{phase=~"Pending|Failed|Unknown"})', thresholds=REDPOS, bg=True), 3, 4),
    (STAT("API up", 'sum(up{job="kube-apiserver"})', thresholds=GREEN), 3, 4),
    (STAT("etcd leader", "min(etcd_server_has_leader)", thresholds=GOODBAD, bg=True, textmode="value"), 3, 4),
    (STAT("CPU used", '100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])))', unit="percent", decimals=1, thresholds=PCT, bg=True), 3, 4),
    (STAT("Mem used", "100 * (1 - sum(node_memory_MemAvailable_bytes)/sum(node_memory_MemTotal_bytes))", unit="percent", decimals=1, thresholds=PCT, bg=True), 3, 4),
])
b.row("At a glance")
b.add([
    (TS("Cluster CPU cores used", [('sum(rate(node_cpu_seconds_total{mode!="idle"}[5m]))', "used cores"),
                                    ('count(node_cpu_seconds_total{mode="idle"})', "total cores")], unit="short"), 8, 7),
    (TS("Cluster memory", [("sum(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes)", "used"),
                            ("sum(node_memory_MemTotal_bytes)", "total")], unit="bytes"), 8, 7),
    (TS("Pods by phase", [("sum by (phase)(kube_pod_status_phase)", "{{phase}}")], stack=True, fill=30), 8, 7),
])
b.add([
    (TS("Ingress req/s (Traefik) & 5xx", [("sum(rate(traefik_entrypoint_requests_total[5m]))", "req/s"),
                                           ('sum(rate(traefik_entrypoint_requests_total{code=~"5.."}[5m]))', "5xx/s")], unit="reqps"), 8, 7),
    (TS("DNS QPS & SERVFAIL", [("sum(rate(coredns_dns_requests_total[5m]))", "queries/s"),
                                ('sum(rate(coredns_dns_responses_total{rcode="SERVFAIL"}[5m]))', "servfail/s")], unit="reqps"), 8, 7),
    (TS("GPU utilisation", [("DCGM_FI_DEV_GPU_UTIL", "{{Hostname}} gpu{{gpu}}")], unit="percent", maxv=100), 8, 7),
])
b.row("Attention")
b.add([
    (STAT("Targets down", "count(up == 0) or vector(0)", thresholds=REDPOS, bg=True), 4, 5),
    (STAT("Pods not ready", 'count(kube_pod_status_ready{condition="true"} == 0) or vector(0)', thresholds=REDPOS, bg=True), 4, 5),
    (STAT("Restarts (1h)", "sum(increase(kube_pod_container_status_restarts_total[1h]))", decimals=0, thresholds=[{"color":"green","value":None},{"color":"yellow","value":5},{"color":"red","value":25}], bg=True), 4, 5),
    (TABLE("Targets currently DOWN", "up == 0", desc="opnsense fw-2 is expected."), 12, 5),
])
b.row("Focused dashboards")
b.add([(TEXT("", "**Drill down:** "
    "[Nodes](/d/talos-nodes) · [Control plane](/d/talos-controlplane) · [Capacity](/d/talos-capacity) · "
    "[Workloads](/d/talos-workloads) · [Runtime](/d/talos-runtime) · [Networking](/d/talos-network) · "
    "[GPU](/d/talos-gpu) · [Ingress](/d/talos-ingress) · [Storage](/d/talos-storage) · "
    "[Databases](/d/talos-databases) · [Certificates](/d/talos-certmanager) · [Observability](/d/talos-victoriametrics)  \n"
    "_Use the **Talos boards** dropdown (top-left) to jump between dashboards with the same time range._"), 24, 3)])
boards.append(b)

# ============================= NODES =============================
b = Board("Talos — Nodes", "talos-nodes", ["talos"], [NODE])
b.row("Utilisation")
b.add([
    (TS("CPU usage % by node", [('100 * (1 - avg by (instance)(rate(node_cpu_seconds_total{mode="idle",instance=~"$node"}[5m])))', "{{instance}}")], unit="percent", maxv=100, table_legend=True), 12, 8),
    (TS("Memory usage % by node", [('100 * (1 - node_memory_MemAvailable_bytes{instance=~"$node"} / node_memory_MemTotal_bytes{instance=~"$node"})', "{{instance}}")], unit="percent", maxv=100, table_legend=True), 12, 8),
])
b.add([
    (TS("Load1 per core", [('node_load1{instance=~"$node"} / count by (instance)(node_cpu_seconds_total{mode="idle",instance=~"$node"})', "{{instance}}")], desc="Normalised to cores; >1 = run-queue exceeds CPUs."), 8, 8),
    (TS("CPU by mode (cluster)", [('sum by (mode)(rate(node_cpu_seconds_total{mode!="idle",instance=~"$node"}[5m]))', "{{mode}}")], stack=True, fill=30), 8, 8),
    (TS("Memory available by node", [('node_memory_MemAvailable_bytes{instance=~"$node"}', "{{instance}}")], unit="bytes"), 8, 8),
])
b.row("Disk & network")
b.add([
    (TS("Filesystem used % by mount", [('100 * (1 - node_filesystem_avail_bytes{instance=~"$node",fstype!~"tmpfs|ramfs|overlay"} / node_filesystem_size_bytes{instance=~"$node",fstype!~"tmpfs|ramfs|overlay"})', "{{instance}} {{mountpoint}}")], unit="percent", maxv=100, desc="Pseudo filesystems filtered."), 12, 8),
    (TS("Disk I/O utilisation by node", [('sum by (instance)(rate(node_disk_io_time_seconds_total{instance=~"$node"}[5m]))', "{{instance}}")], unit="percentunit", desc="Fraction of time disks were busy."), 12, 8),
])
b.add([
    (TS("Network receive", [('sum by (instance)(rate(node_network_receive_bytes_total{instance=~"$node"}[5m]))', "{{instance}}")], unit="Bps"), 8, 8),
    (TS("Network transmit", [('sum by (instance)(rate(node_network_transmit_bytes_total{instance=~"$node"}[5m]))', "{{instance}}")], unit="Bps"), 8, 8),
    (TS("Conntrack entries", [('node_nf_conntrack_entries{instance=~"$node"}', "{{instance}}")], unit="short"), 8, 8),
])
b.row("Inventory")
b.add([
    (STAT("Uptime (min node)", "min(time() - node_boot_time_seconds)", unit="s", textmode="value"), 6, 4),
    (TABLE("Nodes", 'node_uname_info{instance=~"$node"}', desc="Kernel / OS per node."), 18, 4),
])
boards.append(b)

# ============================= CONTROL PLANE =============================
b = Board("Talos — Control Plane", "talos-controlplane", ["talos"], [])
b.row("Health")
b.add([
    (STAT("API servers up", 'sum(up{job="kube-apiserver"})', thresholds=GREEN), 4, 4),
    (STAT("Scheduler up", 'sum(up{job="kube-scheduler"})', thresholds=GREEN), 4, 4),
    (STAT("Controller-mgr up", 'sum(up{job="kube-controller-manager"})', thresholds=GREEN), 4, 4),
    (STAT("etcd members", 'count(up{job="etcd"} == 1)', thresholds=GREEN), 4, 4),
    (STAT("etcd has leader", "min(etcd_server_has_leader)", thresholds=GOODBAD, bg=True, textmode="value"), 4, 4),
    (STAT("API 5xx %", '100 * sum(rate(apiserver_request_total{code=~"5.."}[5m])) / clamp_min(sum(rate(apiserver_request_total[5m])),1)', unit="percent", decimals=2, thresholds=[{"color":"green","value":None},{"color":"yellow","value":1},{"color":"red","value":5}], bg=True), 4, 4),
])
b.row("API server")
b.add([
    (TS("Request rate by verb", [("sum by (verb)(rate(apiserver_request_total[5m]))", "{{verb}}")], unit="reqps", table_legend=True), 12, 8),
    (TS("Request rate by resource (top 10)", [("topk(10, sum by (resource)(rate(apiserver_request_total[5m])))", "{{resource}}")], unit="reqps", table_legend=True), 12, 8),
])
b.add([
    (TS("Latency p99 (read verbs)", [('histogram_quantile(0.99, sum by (le)(rate(apiserver_request_duration_seconds_bucket{verb=~"GET|LIST"}[5m])))', "p99")], unit="s"), 8, 8),
    (TS("Latency p99 (write verbs)", [('histogram_quantile(0.99, sum by (le)(rate(apiserver_request_duration_seconds_bucket{verb=~"POST|PUT|PATCH|DELETE"}[5m])))', "p99")], unit="s"), 8, 8),
    (TS("Client→API request rate by code", [("sum by (code)(rate(rest_client_requests_total[5m]))", "{{code}}")], unit="reqps"), 8, 8),
])
b.row("etcd")
b.add([
    (TS("etcd DB size", [("etcd_mvcc_db_total_size_in_bytes", "{{instance}}")], unit="bytes"), 8, 8),
    (TS("WAL fsync p99 / backend commit p99", [("histogram_quantile(0.99, sum by (le)(rate(etcd_disk_wal_fsync_duration_seconds_bucket[5m])))", "wal fsync"),
                                                ("histogram_quantile(0.99, sum by (le)(rate(etcd_disk_backend_commit_duration_seconds_bucket[5m])))", "backend commit")], unit="s", desc="Keep well under 100ms."), 8, 8),
    (TS("Leader changes / proposal failures", [("sum(rate(etcd_server_leader_changes_seen_total[5m]))", "leader changes/s"),
                                                ("sum(rate(etcd_server_proposals_failed_total[5m]))", "proposal failures/s")], unit="short"), 8, 8),
])
b.row("Controllers & scheduler")
b.add([
    (TS("Workqueue depth (top 10)", [("topk(10, workqueue_depth)", "{{name}}")], unit="short"), 12, 8),
    (TS("Workqueue add rate (top 10)", [("topk(10, sum by (name)(rate(workqueue_adds_total[5m])))", "{{name}}")], unit="short"), 12, 8),
])
boards.append(b)

# ============================= WORKLOADS =============================
b = Board("Talos — Workloads", "talos-workloads", ["talos"], [NS])
b.row("Pods")
b.add([
    (STAT("Running", 'sum(kube_pod_status_phase{phase="Running"})', thresholds=GREEN), 4, 4),
    (STAT("Pending", 'sum(kube_pod_status_phase{phase="Pending"})', thresholds=[{"color":"green","value":None},{"color":"yellow","value":1}], bg=True), 4, 4),
    (STAT("Failed", 'sum(kube_pod_status_phase{phase="Failed"})', thresholds=REDPOS, bg=True), 4, 4),
    (STAT("Not ready", 'count(kube_pod_status_ready{condition="true"} == 0) or vector(0)', thresholds=REDPOS, bg=True), 4, 4),
    (STAT("Restarts (1h)", "sum(increase(kube_pod_container_status_restarts_total[1h]))", decimals=0, thresholds=[{"color":"green","value":None},{"color":"yellow","value":5},{"color":"red","value":25}], bg=True), 4, 4),
    (STAT("Namespaces", "count(count by (namespace)(kube_pod_info))"), 4, 4),
])
b.row("Problems")
b.add([
    (TABLE("Pod restarts (top 20, 1h)", "topk(20, sum by (namespace,pod)(increase(kube_pod_container_status_restarts_total[1h])))"), 8, 8),
    (TABLE("Containers waiting", "sum by (namespace,pod,reason)(kube_pod_container_status_waiting_reason) > 0", desc="CrashLoopBackOff / ImagePullBackOff / etc."), 8, 8),
    (TABLE("Last terminated (non-Completed)", 'sum by (namespace,pod,reason)(kube_pod_container_status_last_terminated_reason{reason!="Completed"}) > 0', desc="OOMKilled, Error, etc."), 8, 8),
])
b.row("Controllers")
b.add([
    (TABLE("Deployments not fully available", "(kube_deployment_status_replicas_available / kube_deployment_spec_replicas) < 1", unit="percentunit"), 8, 8),
    (TABLE("StatefulSets not fully ready", "(kube_statefulset_status_replicas_ready / kube_statefulset_replicas) < 1", unit="percentunit"), 8, 8),
    (TABLE("DaemonSets missing pods", "(kube_daemonset_status_number_ready / kube_daemonset_status_desired_number_scheduled) < 1", unit="percentunit"), 8, 8),
])
b.row("Resource usage by namespace")
b.add([
    (TS("CPU by namespace (top 10)", [('topk(10, sum by (namespace)(rate(container_cpu_usage_seconds_total{container!="",namespace=~"$namespace"}[5m])))', "{{namespace}}")], stack=True, fill=25, table_legend=True), 12, 8),
    (TS("Memory by namespace (top 10)", [('topk(10, sum by (namespace)(container_memory_working_set_bytes{container!="",namespace=~"$namespace"}))', "{{namespace}}")], unit="bytes", stack=True, fill=25, table_legend=True), 12, 8),
])
b.add([
    (TABLE("Top pods by CPU", 'topk(15, sum by (namespace,pod)(rate(container_cpu_usage_seconds_total{container!="",namespace=~"$namespace"}[5m])))'), 12, 8),
    (TABLE("Top pods by memory", 'topk(15, sum by (namespace,pod)(container_memory_working_set_bytes{container!="",namespace=~"$namespace"}))', unit="bytes"), 12, 8),
])
boards.append(b)

# ============================= NETWORKING =============================
b = Board("Talos — Networking (DNS & Hubble)", "talos-network", ["talos"], [])
b.row("CoreDNS")
b.add([
    (TS("Query rate by proto", [("sum by (proto)(rate(coredns_dns_requests_total[5m]))", "{{proto}}")], unit="reqps"), 8, 8),
    (TS("Responses by rcode", [("sum by (rcode)(rate(coredns_dns_responses_total[5m]))", "{{rcode}}")], unit="reqps", desc="Watch SERVFAIL / NXDOMAIN."), 8, 8),
    (TS("Latency p99 / cache hit ratio", [("histogram_quantile(0.99, sum by (le)(rate(coredns_dns_request_duration_seconds_bucket[5m])))", "p99 latency"),
                                          ("sum(rate(coredns_cache_hits_total[5m])) / clamp_min(sum(rate(coredns_cache_hits_total[5m]))+sum(rate(coredns_cache_misses_total[5m])),1)", "cache hit ratio")], unit="s"), 8, 8),
])
b.row("Hubble — flows")
b.add([
    (TS("Flows/s by verdict", [("sum by (verdict)(rate(hubble_flows_processed_total[5m]))", "{{verdict}}")], stack=True, fill=20), 8, 8),
    (TS("Drops/s by reason", [("topk(10, sum by (reason)(rate(hubble_drop_total[5m])))", "{{reason}}")], desc="Policy or dataplane drops."), 8, 8),
    (TS("Lost events/s", [("sum by (source)(rate(hubble_lost_events_total[5m]))", "{{source}}")], desc="Hubble ringbuffer loss — sustained >0 means undercounting."), 8, 8),
])
b.row("Hubble — L7 / protocols")
b.add([
    (TS("DNS queries/s (Hubble)", [("topk(10, sum by (query)(rate(hubble_dns_queries_total[5m])))", "{{query}}")], unit="reqps"), 8, 8),
    (TS("TCP flags/s", [("sum by (flag)(rate(hubble_tcp_flags_total[5m]))", "{{flag}}")], desc="SYN/RST rates are handy for spotting churn/scans."), 8, 8),
    (TS("Top destination ports", [("topk(10, sum by (port)(rate(hubble_port_distribution_total[5m])))", "{{port}}")]), 8, 8),
])
boards.append(b)

# ============================= GPU =============================
b = Board("Talos — GPU (DCGM)", "talos-gpu", ["talos"], [NODE])
b.row("Utilisation & memory")
b.add([
    (TS("GPU utilisation %", [('DCGM_FI_DEV_GPU_UTIL{Hostname=~"$node"}', "{{Hostname}} gpu{{gpu}} {{modelName}}")], unit="percent", maxv=100, table_legend=True), 12, 8),
    (TS("GPU memory used %", [('100 * DCGM_FI_DEV_FB_USED{Hostname=~"$node"} / clamp_min(DCGM_FI_DEV_FB_USED{Hostname=~"$node"} + DCGM_FI_DEV_FB_FREE{Hostname=~"$node"},1)', "{{Hostname}} gpu{{gpu}}")], unit="percent", maxv=100), 12, 8),
])
b.row("Thermals & power")
b.add([
    (TS("Temperature", [('DCGM_FI_DEV_GPU_TEMP{Hostname=~"$node"}', "{{Hostname}} gpu{{gpu}}")], unit="celsius"), 8, 8),
    (TS("Power draw", [('DCGM_FI_DEV_POWER_USAGE{Hostname=~"$node"}', "{{Hostname}} gpu{{gpu}}")], unit="watt"), 8, 8),
    (TS("Energy (rate)", [('rate(DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION{Hostname=~"$node"}[5m]) / 1000', "{{Hostname}} gpu{{gpu}}")], unit="watt", desc="Derived from total energy counter (mJ)."), 8, 8),
])
b.row("Clocks & encoder")
b.add([
    (TS("SM / memory clock", [('DCGM_FI_DEV_SM_CLOCK{Hostname=~"$node"}', "{{Hostname}} gpu{{gpu}} sm"),
                              ('DCGM_FI_DEV_MEM_CLOCK{Hostname=~"$node"}', "{{Hostname}} gpu{{gpu}} mem")], unit="MHz"), 8, 8),
    (TS("Encoder / decoder util %", [('DCGM_FI_DEV_ENC_UTIL{Hostname=~"$node"}', "{{Hostname}} gpu{{gpu}} enc"),
                                     ('DCGM_FI_DEV_DEC_UTIL{Hostname=~"$node"}', "{{Hostname}} gpu{{gpu}} dec")], unit="percent", maxv=100, desc="Useful for transcoding (tdarr / Plex)."), 8, 8),
    (TS("Memory-copy util %", [('DCGM_FI_DEV_MEM_COPY_UTIL{Hostname=~"$node"}', "{{Hostname}} gpu{{gpu}}")], unit="percent", maxv=100), 8, 8),
])
boards.append(b)

# ============================= INGRESS =============================
b = Board("Talos — Ingress (Traefik)", "talos-ingress", ["talos"], [])
b.row("Traffic")
b.add([
    (STAT("Total req/s", "sum(rate(traefik_entrypoint_requests_total[5m]))", unit="reqps", decimals=1), 4, 4),
    (STAT("4xx/s", 'sum(rate(traefik_entrypoint_requests_total{code=~"4.."}[5m]))', unit="reqps", decimals=2, thresholds=[{"color":"green","value":None},{"color":"yellow","value":1}], bg=True), 4, 4),
    (STAT("5xx/s", 'sum(rate(traefik_entrypoint_requests_total{code=~"5.."}[5m]))', unit="reqps", decimals=2, thresholds=REDPOS, bg=True), 4, 4),
    (STAT("Open connections", "sum(traefik_entrypoint_open_connections)", decimals=0), 4, 4),
    (STAT("Config reloads (last ok)", "max(traefik_config_last_reload_success)", textmode="value"), 8, 4),
])
b.row("Requests")
b.add([
    (TS("Request rate by entrypoint", [("sum by (entrypoint)(rate(traefik_entrypoint_requests_total[5m]))", "{{entrypoint}}")], unit="reqps", table_legend=True), 12, 8),
    (TS("Responses by status class", [('sum(rate(traefik_entrypoint_requests_total{code=~"2.."}[5m]))', "2xx"),
                                       ('sum(rate(traefik_entrypoint_requests_total{code=~"3.."}[5m]))', "3xx"),
                                       ('sum(rate(traefik_entrypoint_requests_total{code=~"4.."}[5m]))', "4xx"),
                                       ('sum(rate(traefik_entrypoint_requests_total{code=~"5.."}[5m]))', "5xx")], unit="reqps", stack=True, fill=25), 12, 8),
])
b.row("Latency & services")
b.add([
    (TS("Entrypoint latency p99", [("histogram_quantile(0.99, sum by (le,entrypoint)(rate(traefik_entrypoint_request_duration_seconds_bucket[5m])))", "{{entrypoint}}")], unit="s"), 12, 8),
    (TS("Per-service request rate (top 10)", [("topk(10, sum by (service)(rate(traefik_service_requests_total[5m])))", "{{service}}")], unit="reqps", table_legend=True, desc="Backend services behind Traefik."), 12, 8),
])
boards.append(b)

# ============================= STORAGE =============================
b = Board("Talos — Storage", "talos-storage", ["talos"], [NODE])
b.row("Node filesystems")
b.add([
    (TS("Filesystem used % by mount", [('100 * (1 - node_filesystem_avail_bytes{instance=~"$node",fstype!~"tmpfs|ramfs|overlay"} / node_filesystem_size_bytes{instance=~"$node",fstype!~"tmpfs|ramfs|overlay"})', "{{instance}} {{mountpoint}}")], unit="percent", maxv=100), 12, 8),
    (TS("Inodes used % by mount", [('100 * (1 - node_filesystem_files_free{instance=~"$node",fstype!~"tmpfs|ramfs|overlay"} / node_filesystem_files{instance=~"$node",fstype!~"tmpfs|ramfs|overlay"})', "{{instance}} {{mountpoint}}")], unit="percent", maxv=100), 12, 8),
])
b.row("Kubernetes volumes (KSM)")
b.add([
    (TS("PVCs by phase", [("sum by (phase)(kube_persistentvolumeclaim_status_phase)", "{{phase}}")], stack=True, fill=30), 8, 8),
    (TS("PVs by phase", [("sum by (phase)(kube_persistentvolume_status_phase)", "{{phase}}")], stack=True, fill=30), 8, 8),
    (TABLE("Requested storage by namespace", "sum by (namespace)(kube_persistentvolumeclaim_resource_requests_storage_bytes)", unit="bytes", desc="Live PVC usage isn't exposed (kubelet volume stats empty); this is requested size."), 8, 8),
])
b.row("Garage (S3)")
b.add([
    (TS("Garage disk used % by node", [("100 * (1 - garage_local_disk_avail / clamp_min(garage_local_disk_total,1))", "{{instance}}")], unit="percent", maxv=100), 12, 8),
    (TS("Garage disk available", [("garage_local_disk_avail", "{{instance}}")], unit="bytes"), 12, 8),
])
b.row("TrueNAS")
b.add([
    (TS("Disk temperature", [("truenas_exporter_node_hwmon_temp_celsius", "{{chip}} {{sensor}}")], unit="celsius"), 8, 8),
    (TS("Disk read/write", [("sum(rate(truenas_exporter_node_disk_read_bytes_total[5m]))", "read"),
                            ("sum(rate(truenas_exporter_node_disk_written_bytes_total[5m]))", "write")], unit="Bps"), 8, 8),
    (TS("NFS throughput", [("rate(truenas_exporter_node_nfsd_disk_bytes_read_total[5m])", "read"),
                           ("rate(truenas_exporter_node_nfsd_disk_bytes_written_total[5m])", "write")], unit="Bps"), 8, 8),
])
boards.append(b)

# ============================= DATABASES =============================
b = Board("Talos — Databases", "talos-databases", ["talos"], [NS])
b.row("PostgreSQL (CloudNativePG)")
b.add([
    (TS("Connections by pod", [('sum by (pod)(cnpg_backends_total{namespace=~"$namespace"})', "{{pod}}")], table_legend=True), 8, 8),
    (TS("Database size", [('topk(10, cnpg_pg_database_size_bytes{namespace=~"$namespace"})', "{{namespace}}/{{datname}}")], unit="bytes"), 8, 8),
    (TS("Replication lag", [('cnpg_pg_replication_lag{namespace=~"$namespace"}', "{{pod}}")], unit="s", desc="Streaming replica lag."), 8, 8),
])
b.add([
    (TS("Cache hit ratio", [('sum by (pod)(rate(cnpg_cache_hits{namespace=~"$namespace"}[5m])) / clamp_min(sum by (pod)(rate(cnpg_cache_hits{namespace=~"$namespace"}[5m]) + rate(cnpg_cache_miss{namespace=~"$namespace"}[5m])),1)', "{{pod}}")], unit="percentunit", maxv=1), 8, 8),
    (TS("WAL bytes/s", [('sum by (pod)(rate(cnpg_collector_wal_bytes{namespace=~"$namespace"}[5m]))', "{{pod}}")], unit="Bps"), 8, 8),
    (TABLE("Last successful backup age", '(time() - cnpg_collector_last_available_backup_timestamp{namespace=~"$namespace"}) > 0', unit="s", desc="Seconds since last available backup."), 8, 8),
])
b.row("Percona XtraDB / Galera (MySQL)")
b.add([
    (STAT("Galera cluster size", "max(mysql_global_status_wsrep_cluster_size)", thresholds=GREEN, textmode="value"), 4, 4),
    (STAT("wsrep ready", "min(mysql_global_status_wsrep_ready)", thresholds=GOODBAD, bg=True, textmode="value"), 4, 4),
    (STAT("Local state (4=Synced)", "min(mysql_global_status_wsrep_local_state)", thresholds=[{"color":"red","value":None},{"color":"green","value":4}], bg=True, textmode="value"), 4, 4),
    (STAT("MySQL up", "sum(mysql_up)", thresholds=GREEN), 4, 4),
    (STAT("Connections", "sum(mysql_global_status_threads_connected)", decimals=0), 4, 4),
    (STAT("Max connections", "max(mysql_global_variables_max_connections)", decimals=0), 4, 4),
])
b.add([
    (TS("Queries/s (QPS)", [("sum by (pod)(rate(mysql_global_status_queries[5m]))", "{{pod}}")], unit="short"), 8, 8),
    (TS("Threads connected vs max", [("sum(mysql_global_status_threads_connected)", "connected"),
                                     ("max(mysql_global_variables_max_connections)", "max")], unit="short"), 8, 8),
    (TS("Network in/out", [("sum(rate(mysql_global_status_bytes_received[5m]))", "received"),
                           ("sum(rate(mysql_global_status_bytes_sent[5m]))", "sent")], unit="Bps"), 8, 8),
])
b.row("HAProxy (Percona)")
b.add([
    (TS("Frontend / backend sessions", [("sum(haproxy_frontend_current_sessions)", "frontend"),
                                        ("sum(haproxy_backend_current_sessions)", "backend")], unit="short"), 8, 8),
    (TS("HTTP responses by code", [("sum by (code)(rate(haproxy_frontend_http_responses_total[5m]))", "{{code}}")], unit="reqps"), 8, 8),
    (TS("Backend errors/s", [("sum(rate(haproxy_backend_response_errors_total[5m]))", "response errors"),
                             ("sum(rate(haproxy_backend_connection_errors_total[5m]))", "connection errors")], unit="short"), 8, 8),
])
boards.append(b)

# ============================= CERT-MANAGER =============================
b = Board("Talos — Certificates (cert-manager)", "talos-certmanager", ["talos"], [NS])
b.row("Certificates")
b.add([
    (STAT("Certificates", 'count(certmanager_certificate_ready_status{condition="True"})'), 4, 4),
    (STAT("Ready", 'sum(certmanager_certificate_ready_status{condition="True"})', thresholds=GREEN), 4, 4),
    (STAT("Not ready", 'count(certmanager_certificate_ready_status{condition="True"} == 0) or vector(0)', thresholds=REDPOS, bg=True), 4, 4),
    (STAT("Expiring < 14d", 'count((certmanager_certificate_expiration_timestamp_seconds - time()) < (14*86400)) or vector(0)', thresholds=REDPOS, bg=True), 4, 4),
    (STAT("Expiring < 3d", 'count((certmanager_certificate_expiration_timestamp_seconds - time()) < (3*86400)) or vector(0)', thresholds=REDPOS, bg=True), 4, 4),
    (STAT("Sync errors/s", "sum(rate(certmanager_controller_sync_error_count[5m]))", decimals=3, thresholds=REDPOS, bg=True), 4, 4),
])
b.row("Expiry & renewal")
b.add([
    (TABLE("Soonest to expire (days)", 'bottomk(20, (certmanager_certificate_expiration_timestamp_seconds{namespace=~"$namespace"} - time()) / 86400)', desc="Days until each certificate expires — soonest first.", sortdesc=False), 12, 9),
    (TABLE("Certificates not Ready", 'certmanager_certificate_ready_status{condition="True",namespace=~"$namespace"} == 0', desc="Any certificate whose Ready condition is not True."), 12, 9),
])
b.row("Issuance (ACME / Let's Encrypt)")
b.add([
    (TS("ACME request rate by status", [("sum by (status)(rate(certmanager_http_acme_client_request_count[5m]))", "{{status}}")], unit="reqps"), 8, 8),
    (TS("ACME request latency p99", [("histogram_quantile(0.99, sum by (le)(rate(certmanager_http_acme_client_request_duration_seconds_bucket[5m])))", "p99")], unit="s"), 8, 8),
    (TS("Controller sync rate / errors", [("sum(rate(certmanager_controller_sync_call_count[5m]))", "syncs/s"),
                                          ("sum(rate(certmanager_controller_sync_error_count[5m]))", "errors/s")], unit="short"), 8, 8),
])
boards.append(b)

# ============================= OBSERVABILITY (VM/VL) =============================
b = Board("Talos — Observability (VictoriaMetrics)", "talos-victoriametrics", ["talos"], [])
b.row("Ingestion (vmagent)")
b.add([
    (TS("Rows pushed / sec", [("sum(rate(vmagent_remotewrite_global_rows_pushed_before_relabel_total[5m]))", "rows/s")], unit="short"), 8, 8),
    (TS("Remote-write bytes / sec", [("sum(rate(vmagent_remotewrite_bytes_sent_total[5m]))", "bytes/s")], unit="Bps"), 8, 8),
    (TS("Remote-write errors & drops / sec", [("sum(rate(vmagent_remotewrite_errors_total[5m]))", "rw errors"),
                                              ("sum(rate(vmagent_remotewrite_packets_dropped_total[5m]))", "packets dropped")], unit="short", desc="Sustained >0 means data loss to storage."), 8, 8),
])
b.add([
    (STAT("Series dropped by limit (1h)", "sum(increase(vmagent_hourly_series_limit_rows_dropped_total[1h])) or vector(0)", decimals=0, thresholds=REDPOS, bg=True), 6, 4),
    (STAT("Remote-write conns", "sum(vmagent_remotewrite_conns)"), 6, 4),
    (TS("Remote-write latency p99", [("histogram_quantile(0.99, sum by (le)(rate(vmagent_remotewrite_duration_seconds_bucket[5m])))", "p99")], unit="s"), 12, 8),
])
b.row("Query & storage")
b.add([
    (TS("HTTP request rate by path (top 10)", [("topk(10, sum by (path)(rate(vm_http_requests_total[5m])))", "{{path}}")], unit="reqps", table_legend=True), 12, 8),
    (TS("Rollup result cache hit ratio", [("sum(rate(vm_rollup_result_cache_full_hits_total[5m])) / clamp_min(sum(rate(vm_rollup_result_cache_full_hits_total[5m])) + sum(rate(vm_rollup_result_cache_miss_total[5m])),1)", "hit ratio")], unit="percentunit", maxv=1), 12, 8),
])
b.add([
    (TS("Data size on disk", [("sum(vm_data_size_bytes)", "data size")], unit="bytes"), 8, 8),
    (TS("Free disk space", [('vm_free_disk_space_bytes', "{{instance}}")], unit="bytes", desc="vmstorage headroom."), 8, 8),
    (TS("Pending rows / active merges", [("sum(vm_pending_rows)", "pending rows"),
                                         ("sum(vm_active_merges)", "active merges")], unit="short"), 8, 8),
])
b.row("Component health")
b.add([
    (TS("VM / VL targets up by service", [('sum by (service)(up{service=~"victoria-metrics.*|victoria-logs.*"})', "{{service}}")], unit="short", table_legend=True), 12, 8),
    (STAT("Concurrent-select limit reached (5m)", "sum(increase(vm_concurrent_select_limit_reached_total[5m])) or vector(0)", decimals=0, thresholds=REDPOS, bg=True), 12, 8),
])
boards.append(b)

# ============================= RUNTIME (kubelet/containerd) =============================
b = Board("Talos — Runtime (kubelet & containerd)", "talos-runtime", ["talos"], [NODE])
b.row("Kubelet")
b.add([
    (TS("Running pods per node", [('kubelet_running_pods{instance=~"$node"}', "{{instance}}")], unit="short", table_legend=True), 8, 8),
    (TS("Running containers per node", [('kubelet_running_containers{instance=~"$node"}', "{{instance}}")], unit="short"), 8, 8),
    (TS("Pod start rate", [('sum(rate(kubelet_pod_start_duration_seconds_count{instance=~"$node"}[5m]))', "pod starts/s")], unit="short"), 8, 8),
])
b.add([
    (TS("Runtime operations / sec", [('sum by (operation_type)(rate(kubelet_runtime_operations_total{instance=~"$node"}[5m]))', "{{operation_type}}")], unit="short", table_legend=True), 8, 8),
    (TS("Runtime operation errors / sec", [('sum by (operation_type)(rate(kubelet_runtime_operations_errors_total{instance=~"$node"}[5m]))', "{{operation_type}}")], unit="short", desc="Any sustained errors are worth investigating."), 8, 8),
    (TS("PLEG relist p99", [('histogram_quantile(0.99, sum by (le)(rate(kubelet_pleg_relist_duration_seconds_bucket{instance=~"$node"}[5m])))', "p99")], unit="s", desc="High PLEG latency = kubelet under pressure."), 8, 8),
])
b.row("containerd (CRI)")
b.add([
    (TS("CRI op latency p99", [("histogram_quantile(0.99, sum by (le)(rate(containerd_cri_container_create_seconds_bucket[5m])))", "create"),
                               ("histogram_quantile(0.99, sum by (le)(rate(containerd_cri_container_start_seconds_bucket[5m])))", "start"),
                               ("histogram_quantile(0.99, sum by (le)(rate(containerd_cri_container_stop_seconds_bucket[5m])))", "stop")], unit="s"), 12, 8),
    (TS("Container lifecycle ops / sec", [("sum(rate(containerd_cri_container_create_seconds_count[5m]))", "create"),
                                          ("sum(rate(containerd_cri_container_start_seconds_count[5m]))", "start"),
                                          ("sum(rate(containerd_cri_container_stop_seconds_count[5m]))", "stop"),
                                          ("sum(rate(containerd_cri_container_remove_seconds_count[5m]))", "remove")], unit="short"), 12, 8),
])
boards.append(b)

# ============================= CAPACITY & SCHEDULING =============================
b = Board("Talos — Capacity & Scheduling", "talos-capacity", ["talos"], [NS])
b.row("Cluster commitment")
b.add([
    (GAUGE("CPU requests vs allocatable", '100 * sum(kube_pod_container_resource_requests{resource="cpu"}) / clamp_min(sum(kube_node_status_allocatable{resource="cpu"}),1)'), 5, 6),
    (GAUGE("Memory requests vs allocatable", '100 * sum(kube_pod_container_resource_requests{resource="memory"}) / clamp_min(sum(kube_node_status_allocatable{resource="memory"}),1)'), 5, 6),
    (GAUGE("Pods used vs capacity", '100 * count(kube_pod_info) / clamp_min(sum(kube_node_status_capacity{resource="pods"}),1)'), 5, 6),
    (STAT("Pending pods", 'sum(kube_pod_status_phase{phase="Pending"})', thresholds=[{"color":"green","value":None},{"color":"yellow","value":1}], bg=True), 4, 6),
    (STAT("Unschedulable", "sum(kube_pod_status_unschedulable) or vector(0)", thresholds=REDPOS, bg=True), 5, 6),
])
b.row("Per node")
b.add([
    (TS("CPU requests % of allocatable by node", [('100 * sum by (node)(kube_pod_container_resource_requests{resource="cpu"}) / clamp_min(sum by (node)(kube_node_status_allocatable{resource="cpu"}),1)', "{{node}}")], unit="percent", maxv=100, table_legend=True), 8, 8),
    (TS("Memory requests % of allocatable by node", [('100 * sum by (node)(kube_pod_container_resource_requests{resource="memory"}) / clamp_min(sum by (node)(kube_node_status_allocatable{resource="memory"}),1)', "{{node}}")], unit="percent", maxv=100, table_legend=True), 8, 8),
    (TS("Pods per node vs capacity", [("count by (node)(kube_pod_info)", "{{node}} pods"),
                                      ('min by (node)(kube_node_status_capacity{resource="pods"})', "{{node}} capacity")], unit="short"), 8, 8),
])
b.row("By namespace & requests vs limits")
b.add([
    (TABLE("CPU requests by namespace", 'sum by (namespace)(kube_pod_container_resource_requests{resource="cpu",namespace=~"$namespace"})', desc="Cores requested."), 8, 8),
    (TABLE("Memory requests by namespace", 'sum by (namespace)(kube_pod_container_resource_requests{resource="memory",namespace=~"$namespace"})', unit="bytes"), 8, 8),
    (TS("Cluster requests vs limits", [('sum(kube_pod_container_resource_requests{resource="cpu"})', "cpu requests"),
                                       ('sum(kube_pod_container_resource_limits{resource="cpu"})', "cpu limits")], unit="short", desc="Committed vs capped CPU."), 8, 8),
])
boards.append(b)

# ---- write + validate ----
outdir = "/mnt/user-data/outputs/dashboards"
os.makedirs(outdir, exist_ok=True)
summary = []
for b in boards:
    d = b.to_dict()
    fn = os.path.join(outdir, b.uid + ".json")
    with open(fn, "w") as f:
        json.dump(d, f, indent=2)
    # validate
    json.load(open(fn))
    ids = [p["id"] for p in d["panels"]]
    boxes = [(p["gridPos"]["x"], p["gridPos"]["y"], p["gridPos"]["w"], p["gridPos"]["h"]) for p in d["panels"]]
    ov = 0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, bx = boxes[i], boxes[j]
            if a[0] < bx[0]+bx[2] and bx[0] < a[0]+a[2] and a[1] < bx[1]+bx[3] and bx[1] < a[1]+a[3]:
                ov += 1
    npanels = len([p for p in d["panels"] if p["type"] != "row"])
    summary.append((b.uid, len(d["panels"]), npanels, len(set(ids)) == len(ids), ov))

print(f"{'uid':<22}{'items':>6}{'panels':>8}{'uniqIDs':>9}{'overlaps':>9}")
for u, it, np_, uq, ov in summary:
    print(f"{u:<22}{it:>6}{np_:>8}{str(uq):>9}{ov:>9}")
print("\nfiles:", os.listdir(outdir))
