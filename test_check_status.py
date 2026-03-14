"""
Tests básicos para check_status.py
Ejecutar con: python test_check_status.py
"""

import json
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

# Importar el módulo a testear
import check_status

class TestCheckStatus(unittest.TestCase):
    
    def test_service_name(self):
        """Test extracción de nombre de servicio desde URL"""
        self.assertEqual(check_status.service_name("https://damaju.com.co"), "Damaju")
        self.assertEqual(check_status.service_name("https://ops.damaju.com.co/"), "Ops")
        self.assertEqual(check_status.service_name("http://test.example.com"), "Test")
    
    def test_now_iso(self):
        """Test generación de timestamp ISO"""
        result = check_status.now_iso()
        self.assertIsInstance(result, str)
        # Verificar que es parseable
        datetime.fromisoformat(result)
    
    def test_calculate_metrics_empty(self):
        """Test métricas con historial vacío"""
        metrics = check_status.calculate_metrics([])
        self.assertIsNone(metrics['uptime_24h'])
        self.assertIsNone(metrics['uptime_7d'])
        self.assertEqual(metrics['incidents_count'], 0)
    
    def test_calculate_metrics_with_data(self):
        """Test métricas con datos reales"""
        now = datetime.now(timezone.utc)
        history = [
            {"up": True, "response_time": 100, "timestamp": (now - timedelta(hours=1)).isoformat()},
            {"up": True, "response_time": 150, "timestamp": (now - timedelta(hours=2)).isoformat()},
            {"up": False, "response_time": 0, "timestamp": (now - timedelta(hours=3)).isoformat()},
            {"up": True, "response_time": 120, "timestamp": (now - timedelta(hours=4)).isoformat()},
        ]
        
        metrics = check_status.calculate_metrics(history)
        self.assertIsNotNone(metrics['uptime_24h'])
        self.assertEqual(metrics['uptime_24h'], 75.0)  # 3 de 4 están up
        self.assertIsNotNone(metrics['avg_response_time'])
    
    def test_build_alert(self):
        """Test construcción de mensaje de alerta"""
        down_sites = ["https://damaju.com.co", "https://ops.damaju.com.co"]
        timestamp = "2026-03-13T21:40:44+00:00"
        
        message = check_status.build_alert(down_sites, timestamp)
        
        self.assertIn("🔴", message)
        self.assertIn("Damaju Status", message)
        self.assertIn("CAÍDO", message)
        self.assertIn("Damaju", message)
        self.assertIn("Ops", message)
    
    def test_build_recovery_alert(self):
        """Test construcción de mensaje de recuperación"""
        recovered_sites = ["https://damaju.com.co"]
        timestamp = "2026-03-13T21:45:44+00:00"
        
        message = check_status.build_recovery_alert(recovered_sites, timestamp)
        
        self.assertIn("🟢", message)
        self.assertIn("Damaju Status", message)
        self.assertIn("RECUPERADO", message)
        self.assertIn("Damaju", message)
    
    def test_build_alert_many_sites(self):
        """Test construcción de alerta con muchos sitios"""
        down_sites = [
            "https://site1.com",
            "https://site2.com",
            "https://site3.com",
            "https://site4.com",
            "https://site5.com"
        ]
        timestamp = "2026-03-13T21:40:44+00:00"
        
        message = check_status.build_alert(down_sites, timestamp)
        
        # Debe mostrar solo los primeros 3 y "y X más..."
        self.assertIn("y 2 más", message)
    
    @patch('check_status.requests.get')
    def test_check_site_success(self, mock_get):
        """Test check_site con respuesta exitosa"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = check_status.check_site("https://test.com")
        
        self.assertTrue(result['up'])
        self.assertEqual(result['status_code'], 200)
        self.assertIn('response_time', result)
        self.assertIn('timestamp', result)
    
    @patch('check_status.requests.get')
    def test_check_site_timeout(self, mock_get):
        """Test check_site con timeout"""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        result = check_status.check_site("https://test.com")
        
        self.assertFalse(result['up'])
        self.assertEqual(result['status_code'], 0)
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'timeout')
    
    def test_load_status_file_not_exists(self):
        """Test load_status cuando el archivo no existe"""
        with patch.object(Path, 'exists', return_value=False):
            result = check_status.load_status()
            
            self.assertIn('last_updated', result)
            self.assertIn('services', result)
            self.assertEqual(result['services'], {})
    
    def test_save_status(self):
        """Test save_status guarda correctamente"""
        test_data = {
            "last_updated": "2026-03-13T21:40:44+00:00",
            "services": {}
        }
        
        with patch.object(Path, 'write_text') as mock_write:
            check_status.save_status(test_data)
            mock_write.assert_called_once()
            
            # Verificar que el argumento es JSON válido
            written_data = mock_write.call_args[0][0]
            json.loads(written_data)  # No debe lanzar excepción

class TestConfiguration(unittest.TestCase):
    
    def test_config_loaded(self):
        """Test que la configuración se carga correctamente"""
        self.assertIsInstance(check_status.SITES, list)
        self.assertGreater(len(check_status.SITES), 0)
        self.assertIsInstance(check_status.TIMEOUT_SECONDS, int)
        self.assertIsInstance(check_status.MAX_HISTORY, int)

if __name__ == '__main__':
    print("🧪 Ejecutando tests de check_status.py...")
    print("=" * 60)
    
    # Ejecutar tests
    unittest.main(verbosity=2)
