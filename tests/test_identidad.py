"""Una fecha fija, compartida por el prompt y el dashboard."""

import unittest
from datetime import date

from lumi_identidad import FECHA_NACIMIENTO_LUMI, identidad_lumi


class IdentidadLumi(unittest.TestCase):
    def test_fecha_reconocida_por_drako(self):
        self.assertEqual(FECHA_NACIMIENTO_LUMI.isoformat(), "2026-09-10")
        self.assertEqual(identidad_lumi(date(2026, 9, 10))["fecha_nacimiento_texto"],
                         "10 de septiembre de 2026")

    def test_dias_desde_nacimiento(self):
        self.assertEqual(identidad_lumi(date(2026, 9, 10))["dias_desde_nacimiento"], 0)
        self.assertEqual(identidad_lumi(date(2026, 11, 1))["dias_desde_nacimiento"], 52)

    def test_la_fecha_no_depende_del_despliegue(self):
        self.assertEqual(identidad_lumi(date(2027, 9, 10))["fecha_nacimiento"],
                         "2026-09-10")


if __name__ == "__main__":
    unittest.main()
