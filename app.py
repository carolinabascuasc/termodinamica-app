import streamlit as st
import CoolProp.CoolProp as CP

# ==============================
# Conversión de unidades
# ==============================
def to_SI(var, val):
    if var == 'P': return val * 1000  # kPa → Pa
    if var == 'T': return val + 273.15  # °C → K
    if var in ('H', 'U', 'S'): return val * 1000  # kJ/kg → J/kg
    return val

def from_SI(var, val):
    if var == 'P': return val / 1000  # Pa → kPa
    if var == 'T': return val - 273.15  # K → °C
    if var in ('H', 'U', 'S'): return val / 1000  # J/kg → kJ/kg
    return val

# ==============================
# Interfaz Streamlit
# ==============================
st.title("💧 Calculadora Termodinámica General")

fluido = st.selectbox("Selecciona el fluido", ["Water", "Air", "R134a", "R22", "R410A"])

variables = [
    "T (°C)", "P (kPa)", "H (kJ/kg)", "U (kJ/kg)",
    "S (kJ/kg·K)", "V (m³/kg)", "Q (calidad)"
]

v1_label = st.selectbox("Variable 1", variables)
v2_label = st.selectbox("Variable 2", variables, index=1)

v1_val = st.number_input(f"Valor de {v1_label}", format="%.6f")
v2_val = st.number_input(f"Valor de {v2_label}", format="%.6f")

label_to_code = {
    "P (kPa)": "P",
    "T (°C)": "T",
    "H (kJ/kg)": "H",
    "U (kJ/kg)": "U",
    "S (kJ/kg·K)": "S",
    "V (m³/kg)": "V",
    "Q (calidad)": "Q"
}

var1 = label_to_code[v1_label]
var2 = label_to_code[v2_label]

# ==============================
# Función principal de cálculo
# ==============================
def calcular(fluido, var1, val1, var2, val2):
    fluido_CP = fluido.lower() if fluido == "Air" else fluido

    val1_SI = to_SI(var1, val1)
    val2_SI = to_SI(var2, val2)

    # Caso especial: (T, V) o (V, T)
    if set([var1, var2]) == set(["T", "V"]):
        T = val1_SI if var1 == "T" else val2_SI
        V = val1_SI if var1 == "V" else val2_SI
        rho_target = 1 / V

        # Mezcla saturada agua
        if fluido_CP.lower() == "water":
            T_crit = CP.PropsSI("Tcrit","Water")
            if T < T_crit:
                Psat = CP.PropsSI("P","T",T,"Q",0,"Water")
                v_l = 1 / CP.PropsSI("D","T",T,"Q",0,"Water")
                v_v = 1 / CP.PropsSI("D","T",T,"Q",1,"Water")
                if v_l <= V <= v_v:
                    Q = (V - v_l) / (v_v - v_l)
                    h = (1-Q)*CP.PropsSI("H","T",T,"Q",0,"Water") + Q*CP.PropsSI("H","T",T,"Q",1,"Water")
                    u = (1-Q)*CP.PropsSI("U","T",T,"Q",0,"Water") + Q*CP.PropsSI("U","T",T,"Q",1,"Water")
                    s = (1-Q)*CP.PropsSI("S","T",T,"Q",0,"Water") + Q*CP.PropsSI("S","T",T,"Q",1,"Water")
                    P = Psat
                    return {"T":T,"P":P,"V":V,"h":h,"u":u,"s":s,"Q":Q,"region":"Mezcla saturada"}

        # Para otros casos: bisección de presión
        P_low, P_high = 100, 1e8
        for _ in range(100):
            P_mid = (P_low + P_high) / 2
            try:
                rho_mid = CP.PropsSI("D", "T", T, "P", P_mid, fluido_CP)
            except:
                rho_mid = rho_target * 2
            if rho_mid > rho_target:
                P_high = P_mid
            else:
                P_low = P_mid
            if abs(rho_mid - rho_target) / rho_target < 1e-6:
                break
        P = P_mid
        var1, val1_SI = "T", T
        var2, val2_SI = "P", P

    try:
        # Propiedades principales
        T = CP.PropsSI("T", var1, val1_SI, var2, val2_SI, fluido_CP)
        P = CP.PropsSI("P", var1, val1_SI, var2, val2_SI, fluido_CP)
        rho = CP.PropsSI("D", var1, val1_SI, var2, val2_SI, fluido_CP)
        V = 1 / rho
        h = CP.PropsSI("H", var1, val1_SI, var2, val2_SI, fluido_CP)
        u = CP.PropsSI("U", var1, val1_SI, var2, val2_SI, fluido_CP)
        s_raw = CP.PropsSI("S", var1, val1_SI, var2, val2_SI, fluido_CP)

        # Ajuste de entropía para aire
        if fluido_CP == "air":
            s_ref = CP.PropsSI('S','T',273.15,'P',101325,'air')
            s = s_raw - s_ref
        else:
            s = s_raw

        # Determinar región
        Tcrit = CP.PropsSI("Tcrit", fluido_CP)
        Pcrit = CP.PropsSI("Pcrit", fluido_CP)
        Q = None
        if T >= Tcrit or P >= Pcrit:
            region = "Supercrítico / Vapor sobrecalentado"
        else:
            try:
                Psat = CP.PropsSI("P","T",T,"Q",0,fluido_CP)
                v_l = 1 / CP.PropsSI("D","T",T,"Q",0,fluido_CP)
                v_v = 1 / CP.PropsSI("D","T",T,"Q",1,fluido_CP)
                if abs(P - Psat)/Psat < 1e-3 and v_l <= V <= v_v:
                    region = "Mezcla saturada"
                    Q = (V - v_l)/(v_v - v_l)
                elif V < v_l:
                    region = "Líquido comprimido"
                else:
                    region = "Vapor sobrecalentado"
            except:
                region = "Compresible / fuera de saturación"

        return {"T":T,"P":P,"V":V,"h":h,"u":u,"s":s,"Q":Q,"region":region}

    except Exception as e:
        raise ValueError(f"Error al calcular: {e}")

# ==============================
# Ejecución
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
        st.error(e)

