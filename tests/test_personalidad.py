"""Pruebas locales del perfil; no necesita Supabase ni API externas."""

import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


# El módulo de personalidad usa únicamente el acceso privado que ya tiene CIC;
# en esta prueba lo aislamos para no necesitar ni contactar Supabase.
puente_privado = types.ModuleType("lumi_hipotesis_latentes")
puente_privado._cliente_privado = lambda: None
spec = importlib.util.spec_from_file_location(
    "lumi_personalidad_pruebas", Path(__file__).resolve().parents[1] / "lumi_personalidad.py"
)
personalidad = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"lumi_hipotesis_latentes": puente_privado}):
    spec.loader.exec_module(personalidad)


class PruebasPersonalidad(unittest.TestCase):
    def test_opuestos_simetricos_y_catalogo(self):
        for izquierda, derecha in personalidad.PARES:
            self.assertEqual(personalidad.OPUESTOS[izquierda], derecha)
            self.assertEqual(personalidad.OPUESTOS[derecha], izquierda)
        self.assertEqual(len(personalidad.OPUESTOS), 24)

    def test_ningun_rasgo_se_atribuye_sin_pruebas(self):
        perfil = personalidad._filas_a_perfil([])
        self.assertEqual(perfil["rasgos"], [])
        self.assertEqual(perfil["rasgos_activos"], 0)

    def test_desbloqueo_exige_repeticion_dias_y_puntos(self):
        ejemplos = [
            {"rasgo": "observadora", "puntuacion": 36, "apoyos": 3, "dias_con_evidencia": 1},
            {"rasgo": "reflexiva", "puntuacion": 12, "apoyos": 1, "dias_con_evidencia": 2},
            {"rasgo": "autocritica", "puntuacion": 24, "apoyos": 2, "dias_con_evidencia": 2},
        ]
        perfil = personalidad._filas_a_perfil(ejemplos)
        self.assertEqual([r["clave"] for r in perfil["rasgos"]], ["autocritica"])

    def test_puntuacion_cero_desaparece_y_no_crea_opuesto(self):
        perfil = personalidad._filas_a_perfil([
            {"rasgo": "observadora", "puntuacion": 0, "apoyos": 14, "dias_con_evidencia": 7},
            {"rasgo": "despistada", "puntuacion": 0, "apoyos": 0, "dias_con_evidencia": 0},
        ])
        self.assertEqual(perfil["rasgos"], [])

    def test_no_inventa_rasgos_ni_acepta_scores_malformados(self):
        perfil = personalidad._filas_a_perfil([
            {"rasgo": "invulnerable", "puntuacion": 100, "apoyos": 5, "dias_con_evidencia": 5},
            {"rasgo": "observadora", "puntuacion": "falsa", "apoyos": 3, "dias_con_evidencia": 3},
        ])
        self.assertEqual(perfil["rasgos"], [])

    def test_validador_no_confunde_falta_de_datos_con_error(self):
        self.assertIsNone(personalidad._evaluar_observacion_historica({"resultado": "sin_datos"}))
        self.assertEqual(personalidad._evaluar_observacion_historica({"resultado": "ok"}),
                         "observadora")
        self.assertIsNone(personalidad._evaluar_observacion_historica({
            "resultado": "fallo", "fechas_distintas": 0,
        }))
        # Admitir honestamente que faltan recuerdos no es un defecto de atención.
        self.assertIsNone(personalidad._evaluar_observacion_historica({
            "resultado": "fallo", "abstencion": True, "fechas_distintas": 4,
            "cobertura_dias": 30, "fechas_con_14_dias": 2,
        }))

    def test_no_almacena_decisiones_sin_alternativas(self):
        async def ejecutar():
            with patch.object(personalidad, "personalidad_habilitada", return_value=True):
                return await personalidad.registrar_decision_personalidad(
                    {"eleccion": "Pensar", "motivo": "Elegí pensar antes de actuar"},
                    "dashboard", "b3a53674-5b01-4ee3-9378-29be72a0d94b")
        self.assertIsNone(asyncio.run(ejecutar()))

    def test_evidencia_independiente_suma_un_rasgo_y_resta_el_contrario(self):
        escritos = []

        class TablaFalsa:
            def __init__(self, nombre):
                self.nombre = nombre

            def insert(self, payload):
                escritos.append((self.nombre, payload))
                return self

            def execute(self):
                return SimpleNamespace(data=[{"id": "prueba"}])

        class ClienteFalso:
            def table(self, nombre):
                return TablaFalsa(nombre)

        async def ejecutar():
            with patch.object(personalidad, "personalidad_habilitada", return_value=True), \
                 patch.object(personalidad, "_cliente_privado", return_value=ClienteFalso()):
                return await personalidad.registrar_observacion_historica(
                    {"resultado": "ok", "fechas_distintas": 3},
                    "b3a53674-5b01-4ee3-9378-29be72a0d94b")

        self.assertTrue(asyncio.run(ejecutar()))
        self.assertEqual(escritos[0][0], "lumi_personalidad_evidencias")
        filas = escritos[0][1]
        self.assertEqual([(f["rasgo"], f["delta"]) for f in filas], [
            ("observadora", 12), ("despistada", -12),
        ])
        self.assertNotEqual(filas[0]["clave_evento"], filas[1]["clave_evento"])


if __name__ == "__main__":
    unittest.main()
