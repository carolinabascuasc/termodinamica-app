import streamlit as st
import CoolProp.CoolProp as CP

# ==============================
# Conversión de unidades
# ==============================
def to_SI(var, val):
    if var == 'P': return val * 1000      # kPa -> Pa
    if var == 'T': return val + 273.15    # °C -> K
    if var in ('H','U','S'): return val * 1000
    if var == 'V': return val
    if var == 'Q': return val
    return val

def from_SI(var, val):
    if var == 'P': return val / 1000      # Pa -> kPa
    if var == 'T': return val - 273.15    # K -> °C
    if var in ('H','U','S'): return val / 1000  # J/kg -> kJ/kg
    if var == 'V': return val
    if var == 'Q': return val
    return val

# ==============================
# Búsqueda robusta de P para T,V
# ==============================
def find_pressure_for_TV(fluid, T, V, P_min=1e2, P_max=1e8, max_expand=1e9, tol_rel=1e-6, max_iter=200):
    rho_target = 1.0 / V
    def rho_at(P):
        return CP.PropsSI("D", "T", T, "P", P, fluid)

    step = 0
    while True:
        try:
            rho_low = rho_at(P_min)
            rho_high = rho_at(P_max)
            f_low = rho_low - rho_target
            f_high = rho_high - rho_target
            if f_low * f_high <= 0:
                break
        except:
            pass
        step += 1
        if step > 50:
            raise ValueError("No se pudo encontrar un intervalo de presión válido para (T,V).")
        P_min = max(1.0, P_min / 10.0)
        P_max = min(max_expand, P_max * 10.0)

    low, high = P_min, P_max
    for i in range(max_iter):
        mid = 0.5 * (low + high)
        try:
            rho_mid = rho_at(mid)
        except:
            low = 0.9 * low + 0.1 * mid
            high = 0.9 * high + 0.1 * mid
            continue
        err_rel = abs(rho_mid - rho_target) / rho_target
        if err_rel < tol_rel:
            return mid
        if (rho_mid - rho_target) * (rho_low - rho_target) < 0:
            high = mid
            rho_high = rho_mid
        else:
            low = mid
            rho_low = rho_mid
    return mid

# ==============================
# Interfaz Streamlit
# ==============================
st.title("💧 Calculadora Termodinámica con referencia de entropía ajustada")

fluido = st.selectbox(
    "Selecciona el fluido",
    ["Water", "air", "R134a", "R22", "R410A"]
)

variables = ["T (°C)", "P (kPa)", "H (kJ/kg)", "U (kJ/kg)", "S (kJ/kg·K)", "V (m³/kg)", "Q (calidad)"]
v1_label = st.selectbox("Variable 1", variables)
v2_label = st.selectbox("Variable 2", variables, index=1)

v1_val = st.number_input(f"Valor de {v1_label}", format="%.6f")
v2_val = st.number_input(f"Valor de {v2_label}", format="%.6f")

label_to_code = {
    "P (kPa)": "P", "T (°C)": "T", "H (kJ/kg)": "H", "U (kJ/kg)": "U",
    "S (kJ/kg·K)": "S", "V (m³/kg)": "V", "Q (calidad)": "Q"
}
var1 = label_to_code[v1_label]
var2 = label_to_code[v2_label]

# ==============================
# Función principal de cálculo
# ==============================
def calcular(fluido, var1, val1, var2, val2):
    val1_SI = to_SI(var1, val1)
    val2_SI = to_SI(var2, val2)

    # Si el par es (T,V) o (V,T), encontrar P
    if set([var1, var2]) == set(["T", "V"]):
        T = val1_SI if var1 == "T" else val2_SI
        V = val1_SI if var1 == "V" else val2_SI
        P = find_pressure_for_TV(fluido, T, V)
        var1, val1_SI = "T", T
        var2, val2_SI = "P", P

    # Propiedades
    T = CP.PropsSI("T", var1, val1_SI, var2, val2_SI, fluido)
    P = CP.PropsSI("P", var1, val1_SI, var2, val2_SI, fluido)
    rho = CP.PropsSI("D", var1, val1_SI, var2, val2_SI, fluido)
    h = CP.PropsSI("H", var1, val1_SI, var2, val2_SI, fluido)
    u = CP.PropsSI("U", var1, val1_SI, var2, val2_SI, fluido)
    V = 1.0 / rho

    # --------------------------
    # Ajuste de entropía: referencia a 0°C y 1 atm
    # --------------------------
    if fluido == "air":
        T_ref = 273.15
        P_ref = 101325
        s_ref = CP.PropsSI('S','T',T_ref,'P',P_ref,'air')
        s_raw = CP.PropsSI("S", var1, val1_SI, var2, val2_SI, 'air')
        s = s_raw - s_ref  # entropía relativa a 0°C y 1 atm
    else:
        s = CP.PropsSI("S", var1, val1_SI, var2, val2_SI, fluido)

    # --------------------------
    # Determinar región
    # --------------------------
    Tcrit = CP.PropsSI("Tcrit", fluido)
    Pcrit = CP.PropsSI("Pcrit", fluido)
    region = "desconocida"
    Q = None
    if T >= Tcrit or P >= Pcrit:
        region = "Supercrítico / Vapor sobrecalentado"
    else:
        try:
            Psat = CP.PropsSI("P", "T", T, "Q", 0, fluido)
            v_l = 1.0 / CP.PropsSI("D", "T", T, "Q", 0, fluido)
            v_v = 1.0 / CP.PropsSI("D", "T", T, "Q", 1, fluido)
            if abs(P - Psat) / Psat < 1e-6 and v_l <= V <= v_v:
                region = "Mezcla saturada"
                Q = (V - v_l) / (v_v - v_l)
            elif V < v_l:
                region = "Líquido comprimido"
            else:
                region = "Vapor sobrecalentado"
        except Exception:
            region = "Compresible / fuera de saturación"

    return {"T": T, "P": P, "V": V, "h": h, "u": u, "s": s, "Q": Q, "region": region}

# ==============================
# Botón calcular
# ==============================
if st.button("Calcular propiedades"):
    try:
        props = calcular(fluido, var1, v1_val, var2, v2_val)
        st.success(f"Región: {props['region']}")
        st.write(f"🌡️ Temperatura: {from_SI('T', props['T']):.2f} °C")
        st.write(f"📈 Presión: {from_SI('P', props['P']):.2f} kPa")
        st.write(f"📦 Volumen específico: {props['V']:.6f} m³/kg")
        st.write(f"🔥 Entalpía: {from_SI('H', props['h']):.2f} kJ/kg")
        st.write(f"⚙️ Energía interna: {from_SI('U', props['u']):.2f} kJ/kg")
        st.write(f"📊 Entropía: {from_SI('S', props['s']):.4f} kJ/kg·K")
        if props["Q"] is not None:
            st.write(f"💧 Título (x): {props['Q']:.4f}")
    except Exception as e:
        st.error(f"Error: {e}")
