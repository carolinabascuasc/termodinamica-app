import streamlit as st
import CoolProp.CoolProp as CP

# -----------------------------
# Funciones de conversión
# -----------------------------
def to_SI(var, val):
    if var == 'P':
        return val * 1000       # kPa → Pa
    if var == 'T':
        return val + 273.15    # °C → K
    if var in ('H','U'):
        return val * 1000      # kJ/kg → J/kg
    if var == 'S':
        return val * 1000      # kJ/kg·K → J/kg·K
    if var == 'V':
        return val             # m³/kg ya en SI
    if var == 'Q':
        return val
    return val

def from_SI(var, val):
    if var == 'P':
        return val / 1000       # Pa → kPa
    if var == 'T':
        return val - 273.15    # K → °C
    if var in ('H','U'):
        return val / 1000      # J/kg → kJ/kg
    if var == 'S':
        return val / 1000      # J/kg·K → kJ/kg·K
    if var == 'V':
        return val             # m³/kg
    if var == 'Q':
        return val
    return val

# -----------------------------
# Interfaz Streamlit
# -----------------------------
st.title("Calculadora avanzada de propiedades de fluidos")

# Selección de fluido
fluido = st.selectbox("Selecciona el fluido", ["Water","Air","R134a","R22","R410A"])

# Variables disponibles
variables = ["T (°C)","P (kPa)","H (kJ/kg)","U (kJ/kg)","S (kJ/kg·K)","V (m³/kg)","Q (calidad)"]
v1_label = st.selectbox("Selecciona 1ª variable", variables, key="v1")
v2_label = st.selectbox("Selecciona 2ª variable", variables, index=1, key="v2")

# Inputs de usuario
v1_val = st.number_input(f"Ingrese {v1_label}", format="%.6f")
v2_val = st.number_input(f"Ingrese {v2_label}", format="%.6f")

# Mapear etiquetas a código CoolProp
label_to_code = {
    "P (kPa)":"P","T (°C)":"T","H (kJ/kg)":"H","U (kJ/kg)":"U",
    "S (kJ/kg·K)":"S","V (m³/kg)":"V","Q (calidad)":"Q"
}

var1 = label_to_code[v1_label]
var2 = label_to_code[v2_label]

# -----------------------------
# Función para detectar región y propiedades
# -----------------------------
def calcular_propiedades(fluido, var1, val1, var2, val2):
    # Convertir a SI
    val1_SI = to_SI(var1, val1)
    val2_SI = to_SI(var2, val2)
    
    # Casos principales
    try:
        # 1) T y P conocidos
        if var1=="T" and var2=="P" or var1=="P" and var2=="T":
            T = val1_SI if var1=="T" else val2_SI
            P = val1_SI if var1=="P" else val2_SI
            
            # Presión de saturación
            P_sat = CP.PropsSI("P","T",T,"Q",0,fluido)
            v_l = 1/CP.PropsSI("D","T",T,"Q",0,fluido)
            v_v = 1/CP.PropsSI("D","T",T,"Q",1,fluido)
            
            rho = CP.PropsSI("D","T",T,"P",P,fluido)
            V = 1/rho
            
            if V < v_l:
                region = "Líquido comprimido"
                x = None
            elif v_l <= V <= v_v:
                region = "Mezcla saturada"
                x = (V - v_l)/(v_v - v_l)
                P = P_sat
            else:
                region = "Vapor sobrecalentado"
                x = None
        
        # 2) T y V conocidos
        elif var1=="T" and var2=="V" or var1=="V" and var2=="T":
            T = val1_SI if var1=="T" else val2_SI
            V = val1_SI if var1=="V" else val2_SI
            v_l = 1/CP.PropsSI("D","T",T,"Q",0,fluido)
            v_v = 1/CP.PropsSI("D","T",T,"Q",1,fluido)
            P_sat = CP.PropsSI("P","T",T,"Q",0,fluido)
            
            if v_l <= V <= v_v:
                region = "Mezcla saturada"
                x = (V - v_l)/(v_v - v_l)
                P = P_sat
            elif V < v_l:
                region = "Líquido comprimido"
                P = CP.PropsSI("P","T",T,"D",1/V,fluido)
                x = None
            else:
                region = "Vapor sobrecalentado"
                P = CP.PropsSI("P","T",T,"D",1/V,fluido)
                x = None
        
        # 3) P y V conocidos
        elif var1=="P" and var2=="V" or var1=="V" and var2=="P":
            P = val1_SI if var1=="P" else val2_SI
            V = val1_SI if var1=="V" else val2_SI
            rho = 1/V
            T = CP.PropsSI("T","P",P,"D",rho,fluido)
            v_l = 1/CP.PropsSI("D","T",T,"Q",0,fluido)
            v_v = 1/CP.PropsSI("D","T",T,"Q",1,fluido)
            P_sat = CP.PropsSI("P","T",T,"Q",0,fluido)
            
            if v_l <= V <= v_v:
                region = "Mezcla saturada"
                x = (V - v_l)/(v_v - v_l)
                P = P_sat
            elif V < v_l:
                region = "Líquido comprimido"
                x = None
            else:
                region = "Vapor sobrecalentado"
                x = None
        
        else:
            st.error("Esta combinación de variables aún no está implementada.")
            return None
        
        # Calcular h, u, s
        h = CP.PropsSI("H","T",T,"P",P,fluido)
        u = CP.PropsSI("U","T",T,"P",P,fluido)
        s = CP.PropsSI("S","T",T,"P",P,fluido)
        
        return {
            "T": T, "P": P, "V": V,
            "h": h, "u": u, "s": s,
            "x": x, "region": region
        }
    except Exception as e:
        st.error(f"Error al calcular: {e}")
        return None

# -----------------------------
# Botón de cálculo
# -----------------------------
if st.button("Calcular propiedades"):
    props = calcular_propiedades(fluido, var1, v1_val, var2, v2_val)
    if props:
        st.success(f"Región detectada: {props['region']}")
        st.write(f"Temperatura: {from_SI('T',props['T']):.2f} °C")
        st.write(f"Presión: {from_SI('P',props['P']):.2f} kPa")
        st.write(f"Volumen específico: {from_SI('V',props['V']):.6f} m³/kg")
        st.write(f"Entalpía: {from_SI('H',props['h']):.2f} kJ/kg")
        st.write(f"Energía interna: {from_SI('U',props['u']):.2f} kJ/kg")
        st.write(f"Entropía: {from_SI('S',props['s']):.2f} kJ/kg·K")
        if props["x"] is not None:
            st.write(f"Título de vapor: {props['x']:.4f}")
        else:
            st.write("Título de vapor: No aplicable")

