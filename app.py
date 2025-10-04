# app.py
import streamlit as st
from CoolProp.CoolProp import PropsSI
from scipy.optimize import fsolve
import numpy as np

st.set_page_config(page_title="Calculadora Termodinámica", layout="wide")

# -----------------------------
# Utilidades de unidades
# -----------------------------
def to_SI(var, val):
    if var == 'P':
        return val * 1000  # kPa → Pa
    if var == 'T':
        return val + 273.15
    if var in ('H','U'):
        return val * 1000
    if var == 'S':
        return val * 1000
    if var == 'V':  # ahora ya ingresamos en m³/kg
        return val
    if var == 'Q':
        return val
    return val


def from_SI(var, val):
    if var == 'P':
        return val / 1000  # Pa → kPa
    if var == 'T':
        return val - 273.15
    if var in ('H','U'):
        return val / 1000
    if var == 'S':
        return val / 1000
    if var == 'V':
        return val  # ya está en m³/kg
    if var == 'Q':
        return val
    return val


# -----------------------------
# Helper: comprobar si PropsSI funciona para par dado (intento directo)
# -----------------------------
def try_direct_TP(fluid, v1, val1, v2, val2):
    try:
        T = PropsSI('T', v1, val1, v2, val2, fluid)
        P = PropsSI('P', v1, val1, v2, val2, fluid)
        return float(T), float(P)
    except Exception:
        return None

# -----------------------------
# Solvers
# -----------------------------
def solve_with_rho(fluid, prop, target, rho):
    """Resolver 1D en T: PropsSI(prop,'T',T,'D',rho) = target"""
    def residual(T):
        try:
            val = PropsSI(prop, 'T', T, 'D', rho, fluid)
            return val - target
        except Exception:
            return 1e6
    T_guess = 300.0
    T_sol, = fsolve(residual, T_guess, maxfev=200)
    return float(T_sol)

def solve_T_rho_2x2(fluid, var1, val1, var2, val2):
    """
    Solucionador general 2x2: incógnitas T (K) y rho (kg/m3).
    Resuelve:
      f1(T,rho) = PropsSI(var1,'T',T,'D',rho) - val1 = 0
      f2(T,rho) = PropsSI(var2,'T',T,'D',rho) - val2 = 0
    """
    def fun(X):
        T, rho = X
        try:
            f1 = PropsSI(var1, 'T', T, 'D', rho, fluid) - val1
            f2 = PropsSI(var2, 'T', T, 'D', rho, fluid) - val2
            return [f1, f2]
        except Exception:
            # Dar valores grandes para que fsolve cambie
            return [1e6, 1e6]

    # disparadores de inicio razonables
    guesses = [
        (300.0, 1.0),      # aire-like
        (500.0, 0.1),      # vapor-like
        (350.0, 1000.0),   # líquido denso (agua)
        (400.0, 10.0)
    ]
    for T0, rho0 in guesses:
        try:
            sol = fsolve(fun, (T0, rho0), maxfev=500)
            T_sol, rho_sol = float(sol[0]), float(sol[1])
            # validar que PropsSI produce valores cerca de objetivo
            try:
                v1_calc = PropsSI(var1, 'T', T_sol, 'D', rho_sol, fluid)
                v2_calc = PropsSI(var2, 'T', T_sol, 'D', rho_sol, fluid)
                if np.isfinite(v1_calc) and np.isfinite(v2_calc):
                    # Residuales relativamente pequeños
                    if abs((v1_calc - val1)) < 1e-6*np.maximum(1,abs(val1)) + 1e-3 and \
                       abs((v2_calc - val2)) < 1e-6*np.maximum(1,abs(val2)) + 1e-3:
                        return T_sol, rho_sol
                    # aunque no estrictamente pequeños, aceptamos si no error
                    return T_sol, rho_sol
            except Exception:
                continue
        except Exception:
            continue
    raise ValueError("No se pudo resolver T y rho con el solver 2x2.")

# -----------------------------
# Región termodinámica
# -----------------------------
def determinar_region(fluid, T, P):
    # usar tolerancia relativa para comparar con saturación
    try:
        P_sat = PropsSI('P','T',T,'Q',0,fluid)
        tol = 1e-5
        rel_diff = abs(P - P_sat) / max(P_sat, 1.0)
        if rel_diff <= tol:
            # punto en la curva de saturación: determinar calidad
            try:
                x = PropsSI('Q','T',T,'P',P,fluid)
                if 0 < x < 1:
                    return f"Mezcla saturada (x={x:.4f})"
                elif x == 1:
                    return "Vapor saturado"
                elif x == 0:
                    return "Líquido saturado"
                else:
                    return "Saturación (calidad no aplicable)"
            except Exception:
                return "Saturación (calidad no disponible)"
        else:
            if P > P_sat:
                return "Líquido comprimido (subcooled)"
            else:
                return "Vapor sobrecalentado"
    except Exception:
        return "Región no aplicable"

# -----------------------------
# Cálculo general
# -----------------------------
def compute_all_properties(fluid, var1, val1_in, var2, val2_in):
    """Flujo general: convierte unidades, resuelve T,P y calcula todo"""
    # convertir a SI
    val1 = to_SI(var1, val1_in)
    val2 = to_SI(var2, val2_in)

    # si ya tenemos T y P (en SI), usarlos
    if (var1 == 'T' and var2 == 'P') or (var1 == 'P' and var2 == 'T'):
        T = val1 if var1 == 'T' else val2
        P = val2 if var2 == 'P' else val1
    else:
        # primer intento: uso directo PropsSI para conseguir T y P
        direct = try_direct_TP(fluid, var1, val1, var2, val2)
        if direct:
            T, P = direct
        else:
            # casos donde V está dado -> rho conocido -> 1D solve
            if var1 == 'V' or var2 == 'V':
                # obtener rho
                V_SI = val1 if var1 == 'V' else val2
                rho = 1.0 / V_SI
                # la otra variable puede ser U,H,S,P,Q,T
                other_var = var2 if var1 == 'V' else var1
                other_val = val2 if var1 == 'V' else val1
                if other_var == 'T':
                    T = other_val
                    P = PropsSI('P','T',T,'D',rho,fluid)
                elif other_var == 'P':
                    P = other_val
                    T = PropsSI('T','P',P,'D',rho,fluid)
                elif other_var in ('U','H','S','Q'):
                    if other_var == 'Q':
                        # quality + V: quality implies saturation; we can derive T from Q and rho?
                        # more directo: if Q specified and V given, attempt to find T by solving quality eq.
                        def res_T_for_Q(Tg):
                            try:
                                qcalc = PropsSI('Q','T',Tg,'D',rho,fluid)
                                return qcalc - other_val
                            except Exception:
                                return 1e6
                        T = fsolve(res_T_for_Q, 300.0, maxfev=200)[0]
                        P = PropsSI('P','T',T,'D',rho,fluid)
                    else:
                        # solve for T using 1D
                        T = solve_with_rho(fluid, other_var, other_val, rho)
                        P = PropsSI('P','T',T,'D',rho,fluid)
                else:
                    raise ValueError("Combinación con V no soportada.")
            else:
                # caso totalmente general: resolver T y rho simultáneamente (2x2)
                # si una de las variables es P we can include it: f1 = Pcalc - Ptarget, f2 = Propcalc - val
                # adaptamos llamando al solver 2x2 con var1/var2 tal cual
                try:
                    # usar 2x2: si alguna variable es P we'll still evaluate PropsSI(var,'T',T,'D',rho)
                    T, rho = solve_T_rho_2x2(fluid, var1, val1, var2, val2)
                    P = PropsSI('P','T',T,'D',rho,fluid)
                except Exception as e:
                    raise ValueError(f"No se pudo determinar T y P para la combinación dada: {e}")

    # ya tenemos T (K) y P (Pa)
    # calcular propiedades principales
    results = {}
    results['T_K'] = float(T)
    results['P_Pa'] = float(P)

    # convert to engineering units for display
    results_display = {}
    results_display['Temperatura (°C)'] = round(from_SI('T', results['T_K']), 6)
    results_display['Presión (bar)'] = round(from_SI('P', results['P_Pa']), 6)

    # region (usamos fluid generico; funciona para agua y muchos refrigerantes)
    results_display['Región'] = determinar_region(fluid, results['T_K'], results['P_Pa'])

    try:
        rho_calc = PropsSI('D','T',results['T_K'],'P',results['P_Pa'],fluid)
        v = 1.0 / rho_calc
        h = PropsSI('H','T',results['T_K'],'P',results['P_Pa'],fluid)
        u = PropsSI('U','T',results['T_K'],'P',results['P_Pa'],fluid)
        s = PropsSI('S','T',results['T_K'],'P',results['P_Pa'],fluid)
        try:
            q = PropsSI('Q','T',results['T_K'],'P',results['P_Pa'],fluid)
            q_out = round(q,6) if 0 <= q <= 1 else "No aplicable"
        except Exception:
            q_out = "No aplicable"

        results_display['Volumen específico (L/kg)'] = round(from_SI('V', v), 6)
        results_display['Entalpía (kJ/kg)'] = round(from_SI('H', h), 6)
        results_display['Energía interna (kJ/kg)'] = round(from_SI('U', u), 6)
        results_display['Entropía (kJ/kg·K)'] = round(from_SI('S', s), 6)
        results_display['Título de vapor (x)'] = q_out
    except Exception as e:
        raise ValueError(f"Error al calcular propiedades a partir de T,P: {e}")

    return results_display

# -----------------------------
# STREAMLIT UI
# -----------------------------
st.title("📐 Calculadora General de Propiedades Termodinámicas")
st.markdown("Introducir **cualquier par** de variables. La app resolverá T y P automáticamente y mostrará todas las propiedades. Unidad de entrada por defecto: °C, bar, kJ/kg, L/kg.")

with st.sidebar:
    st.header("Configuración")
    fluid = st.selectbox("Fluido", ["Water", "Air", "R134a", "R22", "R410A"])
    st.markdown("Variables soportadas: **P (bar)**, **T (°C)**, **H (kJ/kg)**, **U (kJ/kg)**, **S (kJ/kg·K)**, **V (L/kg)**, **Q (calidad)**")
    st.caption("Nota: para refrigerantes use nombres tal como R134a, R22, etc. para CoolProp.")

col1, col2 = st.columns([1,1])
with col1:
    st.subheader("Variable 1 (entrada)")
    v1 = st.selectbox("Selecciona 1ª variable", ["T (°C)","P (kPa)","H (kJ/kg)","U (kJ/kg)","S (kJ/kg·K)","V (m³/kg)","Q (calidad)"], key="v1")
    val1 = st.number_input("Valor 1", value=100.0, key="val1")
with col2:
    st.subheader("Variable 2 (entrada)")
    v2 = st.selectbox("Selecciona 2ª variable", ["P (kPa)","T (°C)","H (kJ/kg)","U (kJ/kg)","S (kJ/kg·K)","V (m³/kg)","Q (calidad)"], index=1, key="v2")
    val2 = st.number_input("Valor 2", value=1.0, key="val2")

# map display labels to short codes
label_to_code = {
    "P (kPa)": "P", "T (°C)": "T", "H (kJ/kg)": "H", "U (kJ/kg)": "U",
    "S (kJ/kg·K)": "S", "V (m³/kg)": "V", "Q (calidad)": "Q"
}

var1 = label_to_code[v1]
var2 = label_to_code[v2]

st.write("---")
run = st.button("▶ Calcular propiedades")

if run:
    try:
        with st.spinner("Resolviendo... (puede tardar unos segundos para casos iterativos)"):
            out = compute_all_properties(fluid, var1, val1, var2, val2)
        # visual cards
        st.success("Cálculo correcto ✅")
        st.markdown("### Resultados principales")
        c1, c2, c3 = st.columns(3)
        c1.metric("Temperatura (°C)", out['Temperatura (°C)'])
        c1.metric("Presión (bar)", out['Presión (bar)'])
        c2.metric("Región", out['Región'])
        c2.metric("Título (x)", out['Título de vapor (x)'])
        c3.metric("Vol. específico (L/kg)", out['Volumen específico (L/kg)'])
        c3.metric("Entalpía (kJ/kg)", out['Entalpía (kJ/kg)'])

        st.markdown("### Propiedades completas")
        st.table([
            {"Propiedad":"Temperatura (°C)","Valor":out['Temperatura (°C)']},
            {"Propiedad":"Presión (bar)","Valor":out['Presión (bar)']},
            {"Propiedad":"Región","Valor":out['Región']},
            {"Propiedad":"Volumen específico (L/kg)","Valor":out['Volumen específico (L/kg)']},
            {"Propiedad":"Entalpía (kJ/kg)","Valor":out['Entalpía (kJ/kg)']},
            {"Propiedad":"Energía interna (kJ/kg)","Valor":out['Energía interna (kJ/kg)']},
            {"Propiedad":"Entropía (kJ/kg·K)","Valor":out['Entropía (kJ/kg·K)']},
            {"Propiedad":"Título de vapor (x)","Valor":out['Título de vapor (x)']}
        ])

    except Exception as e:
        st.error(f"❌ Error: {e}")
        st.info("Revisa que las variables y valores sean físicamente consistentes y estén dentro del rango del fluido.")

st.markdown("---")
st.caption("Desarrollado con CoolProp + Streamlit. Ejecuta en tu PC y abre la URL desde Safari en tu iPhone (misma red) o despliega en Streamlit Cloud para acceso público.")
