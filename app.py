import streamlit as st
import CoolProp.CoolProp as CP

# ==============================
# Conversión de unidades
# ==============================
def to_SI(var, val):
    if var == 'P': return val * 1000
    if var == 'T': return val + 273.15
    if var in ('H','U','S'): return val * 1000
    return val

def from_SI(var, val):
    if var == 'P': return val / 1000
    if var == 'T': return val - 273.15
    if var in ('H','U','S'): return val / 1000
    return val

# ==============================
# Interfaz Streamlit
# ==============================
st.title("💧 Calculadora Termodinámica General (v4)")

fluido = st.selectbox("Selecciona el fluido", ["Water","Air","R134a","R22","R410A"])
variables = ["T (°C)","P (kPa)","H (kJ/kg)","U (kJ/kg)","S (kJ/kg·K)","V (m³/kg)","Q (calidad)"]
v1_label = st.selectbox("Variable 1", variables)
v2_label = st.selectbox("Variable 2", variables, index=1)
v1_val = st.number_input(f"Valor de {v1_label}", format="%.6f")
v2_val = st.number_input(f"Valor de {v2_label}", format="%.6f")

label_to_code = {
    "P (kPa)":"P","T (°C)":"T","H (kJ/kg)":"H","U (kJ/kg)":"U",
    "S (kJ/kg·K)":"S","V (m³/kg)":"V","Q (calidad)":"Q"
}
var1 = label_to_code[v1_label]
var2 = label_to_code[v2_label]

# ==============================
# Tablas de Cengel simuladas
# ==============================
# Para usar tus datos reales, reemplaza los valores aquí o carga CSV
Cengel_tablas = {
    "R134a": {
        # ejemplo: "T": {P:..., V:..., h:..., u:..., s:..., Q:...}
    },
    "R22": {},
    "R410A": {}
}

def refrigerante_Cengel(fluido, var1, val1, var2, val2):
    # Aquí deberías implementar la búsqueda en la tabla real de Cengel
    # Por ahora se devuelve un ejemplo
    return {
        "T": val1 if var1=="T" else 25+273.15,
        "P": val1*1000 if var1=="P" else 180000,
        "V": 0.00075,
        "h": 184100,
        "u": 35720,
        "s": 940,
        "Q": 0.5,
        "region": "Mezcla saturada"
    }

# ==============================
# Función principal de cálculo
# ==============================
def calcular(fluido, var1, val1, var2, val2):
    if fluido in ["R134a","R22","R410A"]:
        return refrigerante_Cengel(fluido, var1, val1, var2, val2)

    val1_SI = to_SI(var1, val1)
    val2_SI = to_SI(var2, val2)
    fluido_CP = fluido.lower() if fluido=="Air" else fluido

    # === CASO T+V ===
    if set([var1, var2]) == set(["T", "V"]):
        T = val1_SI if var1=="T" else val2_SI
        V = val1_SI if var1=="V" else val2_SI
        rho_target = 1/V
        try:
            Psat = CP.PropsSI("P","T",T,"Q",0,fluido_CP)
            v_l = 1/CP.PropsSI("D","T",T,"Q",0,fluido_CP)
            v_v = 1/CP.PropsSI("D","T",T,"Q",1,fluido_CP)
            if v_l <= V <= v_v:
                Q = (V - v_l)/(v_v - v_l)
                h = (1-Q)*CP.PropsSI("H","T",T,"Q",0,fluido_CP)+Q*CP.PropsSI("H","T",T,"Q",1,fluido_CP)
                u = (1-Q)*CP.PropsSI("U","T",T,"Q",0,fluido_CP)+Q*CP.PropsSI("U","T",T,"Q",1,fluido_CP)
                s = (1-Q)*CP.PropsSI("S","T",T,"Q",0,fluido_CP)+Q*CP.PropsSI("S","T",T,"Q",1,fluido_CP)
                P = Psat
                return {"T":T,"P":P,"V":V,"h":h,"u":u,"s":s,"Q":Q,"region":"Mezcla saturada"}
        except: pass
        # Bisección si no es mezcla
        P_low, P_high = 100, 1e8
        for _ in range(100):
            P_mid = (P_low+P_high)/2
            try:
                rho_mid = CP.PropsSI("D","T",T,"P",P_mid,fluido_CP)
            except:
                rho_mid = rho_target*2
            if rho_mid>rho_target: P_high=P_mid
            else: P_low=P_mid
            if abs(rho_mid-rho_target)/rho_target<1e-6: break
        P = P_mid
        var1, val1_SI = "T", T
        var2, val2_SI = "P", P

    # === CASO P+V ===
    if set([var1,var2])==set(["P","V"]):
        P = val1_SI if var1=="P" else val2_SI
        V = val1_SI if var1=="V" else val2_SI
        rho_target = 1/V
        try:
            v_l = 1/CP.PropsSI("D","P",P,"Q",0,fluido_CP)
            v_v = 1/CP.PropsSI("D","P",P,"Q",1,fluido_CP)
            if v_l<=V<=v_v:
                Q=(V-v_l)/(v_v-v_l)
                T=CP.PropsSI("T","P",P,"Q",Q,fluido_CP)
                h=CP.PropsSI("H","P",P,"Q",Q,fluido_CP)
                u=CP.PropsSI("U","P",P,"Q",Q,fluido_CP)
                s=CP.PropsSI("S","P",P,"Q",Q,fluido_CP)
                return {"T":T,"P":P,"V":V,"h":h,"u":u,"s":s,"Q":Q,"region":"Mezcla saturada"}
        except: pass
        T_low, T_high = 273.15, CP.PropsSI("Tcrit",fluido_CP)
        for _ in range(100):
            T_mid=(T_low+T_high)/2
            try:
                rho_mid=CP.PropsSI("D","T",T_mid,"P",P,fluido_CP)
            except:
                rho_mid=rho_target*2
            if rho_mid>rho_target: T_high=T_mid
            else: T_low=T_mid
            if abs(rho_mid-rho_target)/rho_target<1e-6: break
        T=T_mid
        var1, val1_SI = "T", T
        var2, val2_SI = "P", P

    # ==========================
    # Calcular propiedades principales
    # ==========================
    try:
        T = CP.PropsSI("T",var1,val1_SI,var2,val2_SI,fluido_CP)
        P = CP.PropsSI("P",var1,val1_SI,var2,val2_SI,fluido_CP)
        rho = CP.PropsSI("D",var1,val1_SI,var2,val2_SI,fluido_CP)
        V = 1/rho
        h = CP.PropsSI("H",var1,val1_SI,var2,val2_SI,fluido_CP)
        u = CP.PropsSI("U",var1,val1_SI,var2,val2_SI,fluido_CP)
        s = CP.PropsSI("S",var1,val1_SI,var2,val2_SI,fluido_CP)
        Tcrit=CP.PropsSI("Tcrit",fluido_CP)
        Pcrit=CP.PropsSI("Pcrit",fluido_CP)
        Q=None
        if T>=Tcrit or P>=Pcrit:
            region="Supercrítico / Vapor sobrecalentado"
        else:
            try:
                Psat=CP.PropsSI("P","T",T,"Q",0,fluido_CP)
                v_l=1/CP.PropsSI("D","T",T,"Q",0,fluido_CP)
                v_v=1/CP.PropsSI("D","T",T,"Q",1,fluido_CP)
                if v_l<=V<=v_v and abs(P-Psat)/Psat<1e-3:
                    region="Mezcla saturada"
                    Q=(V-v_l)/(v_v-v_l)
                elif V<v_l:
                    region="Líquido comprimido"
                else:
                    region="Vapor sobrecalentado"
            except:
                region="Compresible / fuera de saturación"

        # Corrección refrigerantes (agua ya)
        if fluido_CP.lower() in ["water"]:
            try:
                u_vapor_sat=CP.PropsSI("U","P",P,"Q",1,fluido_CP)
                if u>u_vapor_sat: region="Vapor sobrecalentado"
            except: pass

        return {"T":T,"P":P,"V":V,"h":h,"u":u,"s":s,"Q":Q,"region":region}

    except Exception as e:
        raise ValueError(f"Error al calcular: {e}")

# ==============================
# Botón de cálculo
# ==============================
if st.button("Calcular propiedades"):
    try:
        props=calcular(fluido,var1,v1_val,var2,v2_val)
        st.success(f"Región detectada: {props['region']}")
        st.write(f"T = {from_SI('T',props['T']):.2f} °C")
        st.write(f"P = {from_SI('P',props['P']):.2f} kPa")
        st.write(f"v = {props['V']:.6f} m³/kg")
        st.write(f"h = {from_SI('H',props['h']):.2f} kJ/kg")
        st.write(f"u = {from_SI('U',props['u']):.2f} kJ/kg")
        st.write(f"s = {from_SI('S',props['s']):.4f} kJ/kg·K")
        if props["Q"] is not None:
            st.write(f"x = {props['Q']:.4f}")
    except Exception as e:
        st.error(f"Error al calcular propiedades: {e}")
