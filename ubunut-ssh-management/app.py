import streamlit as st
import yaml
from PIL import Image
import base64
from io import BytesIO
import subprocess

# --- Helper Functions ---
def logo_to_base64(logo):
    if not logo:
        return ""
    buffered = BytesIO()
    logo.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def load_logo(service_name):
    logo_map = {
        "kubernetes": "assets/kubernetes-logo.png",
        "k8s": "assets/kubernetes-logo.png",
        "kube": "assets/kubernetes-logo.png",
        "ceph": "assets/ceph-logo.png",
        "harbor": "assets/harbor-logo.png"
    }
    service_key = service_name.lower()
    for key in logo_map:
        if key in service_key:
            try:
                return Image.open(logo_map[key])
            except:
                return None
    return None

# --- SSH Target Rules ---
def get_extra_ssh_target(environment, service_name):
    env = environment.lower()
    svc = service_name.lower()

    rules = [
        (env == "sandbox" and "kubernetes" in svc, "10.248.35.154"),
        (env == "sandbox" and "ceph" in svc, "10.248.35.204"),
        (env == "pardis" and "kubernetes" in svc, "192.168.114.102"),
        (env == "pardis" and "ceph" in svc, "192.168.114.157"),
        (env == "sandbox-dotin" and "kubernetes" in svc, "10.248.35.220"),
        (env == "sandbox-dotin" and "ceph" in svc, "10.248.35.240"),
        (env == "sandboxapplication" and "kubernetes" in svc, "10.248.35.224"),
        (env == "ceph-podspace-pardis" and "ceph" in svc, "192.168.115.23"),
        (env == "ceph-podspace-sandbox" and "ceph" in svc, "10.248.35.142"),
        (env == "iaas" and "kubernetes" in svc, "10.248.149.42")
    ]

    for condition, target in rules:
        if condition:
            return target
    return None

# --- UI Config ---
st.set_page_config(page_title="Hosts Dashboard", layout="wide", page_icon="🌐")
st.title("🌐 Host Management System")

# --- CSS Styling ---
st.markdown("""
<style>
    .host-card {
        border-radius: 12px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        background: white !important;
        border: 1px solid #e0e0e0 !important;
    }
    .ip-address {
        font-family: monospace;
        font-weight: bold;
        font-size: 14px;
        color: #333333 !important;
    }
    .hostname {
        font-family: monospace;
        color: #555555 !important;
        font-size: 13px;
    }
    .service-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #f8f9fa;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.85em;
        margin-top: 8px;
        border: 1px solid #e0e0e0;
        font-weight: 500;
    }
    .env-badge {
        background: #6c757d;
        color: white !important;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75em;
        font-weight: 500;
    }
    .logo-img {
        width: 18px;
        height: 18px;
        object-fit: contain;
    }
</style>
""", unsafe_allow_html=True)

# --- Data Loading ---
with open('hosts.yaml', 'r') as file:
    data = yaml.safe_load(file)

# --- Core Display Logic ---
def display_nodes(nodes, service_name, environment):
    logo = load_logo(service_name)
    logo_base64 = logo_to_base64(logo) if logo else ""

    service_colors = {
        "kubernetes": "#326ce5",
        "k8s": "#326ce5",
        "kube": "#326ce5",
        "ceph": "#ef5d29",
        "harbor": "#60b932",
        "default": "#555555"
    }

    service_key = service_name.lower()
    color = service_colors.get("default")
    for key in service_colors:
        if key in service_key:
            color = service_colors[key]
            break

    extra_target = get_extra_ssh_target(environment, service_name)

    cols = st.columns(3)
    for idx, node in enumerate(nodes):
        with cols[idx % 3]:
            ip = node["ip"]
            hostname = node["hostname"]
            logo_html = f'<img src="data:image/png;base64,{logo_base64}" class="logo-img">' if logo_base64 else ""

            st.markdown(
                f"""
                <div class="host-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="env-badge">{environment}</span>
                        <span class="service-badge" style="color: {color}">
                            {logo_html} {service_name}
                        </span>
                    </div>
                    <p style="margin: 10px 0 5px 0;"><span class="ip-address">{ip}</span></p>
                    <p><span class="hostname">{hostname}</span></p>
                </div>
                """,
                unsafe_allow_html=True
            )
            button_cols = st.columns([1, 1]) 
            with button_cols[0]:
                if st.button(f"🔗 SSH to {ip}", key=f"ssh_main_{ip}_{idx}"):
                    subprocess.Popen(["./open_ssh.sh", ip])

            if extra_target:
                with button_cols[1]:
                    if st.button(f"🛰 SSH to Main Node", key=f"ssh_extra_{ip}_{idx}"):
                        subprocess.Popen(["./open_ssh.sh", extra_target])

# --- Search Box ---
search_term = st.text_input("🔍 Global Search (IP/Hostname)", placeholder="Search across all hosts...")

# --- Display ---
if search_term:
    matched_nodes = []
    for env in data['environments']:
        for service in env['services']:
            service_name = service['name']
            for node in service['nodes']:
                if (search_term.lower() in node['ip'].lower()) or (search_term.lower() in node['hostname'].lower()):
                    matched_nodes.append({
                        **node,
                        "environment": env['name'],
                        "service": service_name
                    })

    if matched_nodes:
        st.success(f"🔍 Found {len(matched_nodes)} matching hosts")
        grouped = {}
        for node in matched_nodes:
            key = (node['environment'], node['service'])
            grouped.setdefault(key, []).append(node)

        for (env, service), nodes in grouped.items():
            with st.expander(f"{env} › {service} ({len(nodes)} hosts)", expanded=True):
                display_nodes(nodes, service, env)
    else:
        st.warning("No matching hosts found")
else:
    st.sidebar.header("Filters")
    selected_env = st.sidebar.selectbox(
        "Select Environment",
        [env['name'] for env in data['environments']],
        index=0
    )

    env_services = []
    for env in data['environments']:
        if env['name'] == selected_env:
            env_services = [service['name'] for service in env['services']]

    selected_service = st.sidebar.selectbox(
        "Select Service",
        env_services,
        index=0
    )

    for env in data['environments']:
        if env['name'] == selected_env:
            for service in env['services']:
                if service['name'] == selected_service:
                    st.header(f"{env['name']} › {selected_service}")
                    display_nodes(service['nodes'], selected_service, env['name'])
