"""
Anomaly Detection Microservice for Outage Detection
Uses machine learning and statistical methods to detect anomalies in service metrics
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
import logging
from dataclasses import dataclass
import math
import statistics

# ML imports
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import DBSCAN
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

from stream_processor import OutageEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AnomalyResult:
    """Result of anomaly detection"""
    is_anomaly: bool
    confidence_score: float
    severity: str
    method: str
    baseline_value: float
    current_value: float
    threshold: float
    timestamp: str

class BaselineCalculator:
    """Calculate baseline metrics for services"""
    
    def __init__(self):
        self.baselines = {}
    
    def calculate_baseline(self, service_id: int, historical_data: List[Dict]) -> Dict:
        """Calculate baseline metrics from historical data"""
        if not historical_data:
            return self._default_baseline()
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(historical_data)
        
        if df.empty:
            return self._default_baseline()
        
        # Calculate time-based baselines
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        
        baseline = {}
        
        # Calculate hourly baselines
        hourly_stats = df.groupby('hour').agg({
            'report_count': ['mean', 'std', 'max'],
            'response_time': ['mean', 'std', 'max']
        }).fillna(0)
        
        baseline['hourly'] = {}
        for hour in range(24):
            if hour in hourly_stats.index:
                baseline['hourly'][hour] = {
                    'report_count_mean': float(hourly_stats.loc[hour, ('report_count', 'mean')]),
                    'report_count_std': float(hourly_stats.loc[hour, ('report_count', 'std')]),
                    'response_time_mean': float(hourly_stats.loc[hour, ('response_time', 'mean')]),
                    'response_time_std': float(hourly_stats.loc[hour, ('response_time', 'std')])
                }
            else:
                baseline['hourly'][hour] = self._default_hour_baseline()
        
        # Calculate daily baselines
        daily_stats = df.groupby('day_of_week').agg({
            'report_count': ['mean', 'std'],
            'response_time': ['mean', 'std']
        }).fillna(0)
        
        baseline['daily'] = {}
        for day in range(7):
            if day in daily_stats.index:
                baseline['daily'][day] = {
                    'report_count_mean': float(daily_stats.loc[day, ('report_count', 'mean')]),
                    'report_count_std': float(daily_stats.loc[day, ('report_count', 'std')]),
                    'response_time_mean': float(daily_stats.loc[day, ('response_time', 'mean')]),
                    'response_time_std': float(daily_stats.loc[day, ('response_time', 'std')])
                }
            else:
                baseline['daily'][day] = self._default_hour_baseline()
        
        # Overall statistics
        baseline['overall'] = {
            'report_count_mean': float(df['report_count'].mean()),
            'report_count_std': float(df['report_count'].std()),
            'response_time_mean': float(df['response_time'].mean()),
            'response_time_std': float(df['response_time'].std()),
            'total_samples': len(df)
        }
        
        # Store in cache
        self.baselines[service_id] = baseline
        
        return baseline
    
    def _default_baseline(self) -> Dict:
        """Default baseline when no historical data"""
        return {
            'hourly': {hour: self._default_hour_baseline() for hour in range(24)},
            'daily': {day: self._default_hour_baseline() for day in range(7)},
            'overall': {
                'report_count_mean': 5.0,
                'report_count_std': 2.0,
                'response_time_mean': 200.0,
                'response_time_std': 50.0,
                'total_samples': 0
            }
        }
    
    def _default_hour_baseline(self) -> Dict:
        """Default hourly baseline"""
        return {
            'report_count_mean': 5.0,
            'report_count_std': 2.0,
            'response_time_mean': 200.0,
            'response_time_std': 50.0
        }
    
    def get_baseline(self, service_id: int, timestamp: datetime) -> Dict:
        """Get baseline for specific time"""
        if service_id not in self.baselines:
            return self._default_baseline()['overall']
        
        baseline = self.baselines[service_id]
        hour = timestamp.hour
        day = timestamp.weekday()
        
        # Combine hourly and daily baselines
        hourly_baseline = baseline['hourly'].get(hour, self._default_hour_baseline())
        daily_baseline = baseline['daily'].get(day, self._default_hour_baseline())
        
        # Weight hourly baseline more heavily
        return {
            'report_count_mean': hourly_baseline['report_count_mean'] * 0.7 + daily_baseline['report_count_mean'] * 0.3,
            'report_count_std': max(hourly_baseline['report_count_std'], daily_baseline['report_count_std']),
            'response_time_mean': hourly_baseline['response_time_mean'] * 0.7 + daily_baseline['response_time_mean'] * 0.3,
            'response_time_std': max(hourly_baseline['response_time_std'], daily_baseline['response_time_std'])
        }

class StatisticalAnomalyDetector:
    """Statistical methods for anomaly detection"""
    
    def __init__(self, threshold_multiplier: float = 3.0):
        self.threshold_multiplier = threshold_multiplier
        self.baseline_calculator = BaselineCalculator()
    
    def detect_z_score_anomaly(self, service_id: int, current_value: float, 
                              metric_type: str, timestamp: datetime) -> AnomalyResult:
        """Detect anomaly using Z-score method"""
        baseline = self.baseline_calculator.get_baseline(service_id, timestamp)
        
        mean_key = f"{metric_type}_mean"
        std_key = f"{metric_type}_std"
        
        baseline_mean = baseline.get(mean_key, 0)
        baseline_std = baseline.get(std_key, 1)
        
        if baseline_std == 0:
            baseline_std = 1  # Avoid division by zero
        
        z_score = abs(current_value - baseline_mean) / baseline_std
        threshold = self.threshold_multiplier
        
        is_anomaly = z_score > threshold
        confidence_score = min(z_score / threshold, 1.0) if is_anomaly else 0.0
        
        # Determine severity
        if z_score > threshold * 2:
            severity = "critical"
        elif z_score > threshold * 1.5:
            severity = "high"
        elif z_score > threshold:
            severity = "medium"
        else:
            severity = "low"
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            confidence_score=confidence_score,
            severity=severity,
            method="z_score",
            baseline_value=baseline_mean,
            current_value=current_value,
            threshold=threshold,
            timestamp=timestamp.isoformat()
        )
    
    def detect_iqr_anomaly(self, service_id: int, recent_values: List[float], 
                          current_value: float, timestamp: datetime) -> AnomalyResult:
        """Detect anomaly using Interquartile Range method"""
        if len(recent_values) < 4:
            # Not enough data, return no anomaly
            return AnomalyResult(
                is_anomaly=False,
                confidence_score=0.0,
                severity="low",
                method="iqr",
                baseline_value=0.0,
                current_value=current_value,
                threshold=0.0,
                timestamp=timestamp.isoformat()
            )
        
        q1 = np.percentile(recent_values, 25)
        q3 = np.percentile(recent_values, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        is_anomaly = current_value < lower_bound or current_value > upper_bound
        
        if is_anomaly:
            if current_value > upper_bound:
                distance = current_value - upper_bound
                max_distance = iqr * 2  # Normalize
            else:
                distance = lower_bound - current_value
                max_distance = iqr * 2
            
            confidence_score = min(distance / max_distance, 1.0) if max_distance > 0 else 1.0
            
            if distance > iqr * 3:
                severity = "critical"
            elif distance > iqr * 2:
                severity = "high"
            elif distance > iqr:
                severity = "medium"
            else:
                severity = "low"
        else:
            confidence_score = 0.0
            severity = "low"
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            confidence_score=confidence_score,
            severity=severity,
            method="iqr",
            baseline_value=np.median(recent_values),
            current_value=current_value,
            threshold=upper_bound,
            timestamp=timestamp.isoformat()
        )

class MachineLearningAnomalyDetector:
    """Machine learning-based anomaly detection"""
    
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.trained_services = set()
    
    def train_isolation_forest(self, service_id: int, historical_data: List[Dict]) -> bool:
        """Train Isolation Forest model for a service"""
        if not ML_AVAILABLE:
            logger.warning("Scikit-learn not available for ML anomaly detection")
            return False
        
        if not historical_data or len(historical_data) < 20:
            logger.warning(f"Insufficient data to train model for service {service_id}")
            return False
        
        try:
            # Prepare data
            df = pd.DataFrame(historical_data)
            features = ['report_count', 'response_time']
            
            # Handle missing values
            for feature in features:
                if feature not in df.columns:
                    df[feature] = 0
                df[feature] = df[feature].fillna(0)
            
            X = df[features].values
            
            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Train Isolation Forest
            model = IsolationForest(
                contamination=0.1,  # Expect 10% anomalies
                random_state=42,
                n_estimators=100
            )
            model.fit(X_scaled)
            
            # Store model and scaler
            self.models[service_id] = model
            self.scalers[service_id] = scaler
            self.trained_services.add(service_id)
            
            logger.info(f"Isolation Forest trained for service {service_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error training Isolation Forest for service {service_id}: {e}")
            return False
    
    def detect_ml_anomaly(self, service_id: int, report_count: float, 
                         response_time: float, timestamp: datetime) -> AnomalyResult:
        """Detect anomaly using trained ML model"""
        if not ML_AVAILABLE or service_id not in self.models:
            return AnomalyResult(
                is_anomaly=False,
                confidence_score=0.0,
                severity="low",
                method="ml_isolation_forest",
                baseline_value=0.0,
                current_value=0.0,
                threshold=0.0,
                timestamp=timestamp.isoformat()
            )
        
        try:
            model = self.models[service_id]
            scaler = self.scalers[service_id]
            
            # Prepare input
            X = np.array([[report_count, response_time]])
            X_scaled = scaler.transform(X)
            
            # Predict
            prediction = model.predict(X_scaled)[0]
            anomaly_score = model.decision_function(X_scaled)[0]
            
            is_anomaly = prediction == -1  # -1 indicates anomaly
            
            # Convert anomaly score to confidence (score is typically negative for anomalies)
            confidence_score = max(0, min(1, abs(anomaly_score)))
            
            # Determine severity based on anomaly score
            if abs(anomaly_score) > 0.5:
                severity = "critical"
            elif abs(anomaly_score) > 0.3:
                severity = "high"
            elif abs(anomaly_score) > 0.1:
                severity = "medium"
            else:
                severity = "low"
            
            return AnomalyResult(
                is_anomaly=is_anomaly,
                confidence_score=confidence_score,
                severity=severity,
                method="ml_isolation_forest",
                baseline_value=0.0,  # ML model doesn't have explicit baseline
                current_value=max(report_count, response_time),
                threshold=0.0,
                timestamp=timestamp.isoformat()
            )
            
        except Exception as e:
            logger.error(f"Error in ML anomaly detection for service {service_id}: {e}")
            return AnomalyResult(
                is_anomaly=False,
                confidence_score=0.0,
                severity="low",
                method="ml_isolation_forest",
                baseline_value=0.0,
                current_value=0.0,
                threshold=0.0,
                timestamp=timestamp.isoformat()
            )

class HybridAnomalyDetector:
    """Combines multiple anomaly detection methods"""
    
    def __init__(self):
        self.statistical_detector = StatisticalAnomalyDetector()
        self.ml_detector = MachineLearningAnomalyDetector()
        self.baseline_calculator = BaselineCalculator()
    
    def train_models(self, service_id: int, historical_data: List[Dict]):
        """Train all models for a service"""
        # Train baseline calculator
        self.baseline_calculator.calculate_baseline(service_id, historical_data)
        
        # Train ML model
        self.ml_detector.train_isolation_forest(service_id, historical_data)
    
    def detect_anomaly(self, service_id: int, report_count: float, 
                      response_time: float, recent_values: List[float] = None,
                      timestamp: datetime = None) -> Dict:
        """Run comprehensive anomaly detection"""
        if timestamp is None:
            timestamp = datetime.now()
        
        if recent_values is None:
            recent_values = []
        
        results = {}
        
        # Statistical methods
        z_score_result = self.statistical_detector.detect_z_score_anomaly(
            service_id, report_count, "report_count", timestamp
        )
        results['z_score'] = z_score_result
        
        response_time_result = self.statistical_detector.detect_z_score_anomaly(
            service_id, response_time, "response_time", timestamp
        )
        results['response_time_z'] = response_time_result
        
        # IQR method
        if recent_values:
            iqr_result = self.statistical_detector.detect_iqr_anomaly(
                service_id, recent_values, report_count, timestamp
            )
            results['iqr'] = iqr_result
        
        # ML method
        ml_result = self.ml_detector.detect_ml_anomaly(
            service_id, report_count, response_time, timestamp
        )
        results['ml'] = ml_result
        
        # Aggregate results
        anomaly_votes = sum(1 for result in results.values() if result.is_anomaly)
        total_methods = len(results)
        
        # Weighted confidence score
        weighted_confidence = sum(
            result.confidence_score * (2 if result.method.startswith('ml') else 1)
            for result in results.values()
        ) / (total_methods + sum(1 for result in results.values() if result.method.startswith('ml')))
        
        # Determine final severity
        severities = [result.severity for result in results.values() if result.is_anomaly]
        if 'critical' in severities:
            final_severity = 'critical'
        elif 'high' in severities:
            final_severity = 'high'
        elif 'medium' in severities:
            final_severity = 'medium'
        else:
            final_severity = 'low'
        
        is_final_anomaly = anomaly_votes >= (total_methods // 2 + 1)  # Majority vote
        
        return {
            'is_anomaly': is_final_anomaly,
            'confidence_score': weighted_confidence,
            'severity': final_severity,
            'method_results': {k: v.__dict__ for k, v in results.items()},
            'votes': f"{anomaly_votes}/{total_methods}",
            'timestamp': timestamp.isoformat()
        }

# Microservice function for external API calls
def analyze_service_anomaly(service_id: int, report_count: float, response_time: float,
                           historical_data: List[Dict] = None) -> Dict:
    """Main function for anomaly detection microservice"""
    detector = HybridAnomalyDetector()
    
    # Train with historical data if provided
    if historical_data:
        detector.train_models(service_id, historical_data)
    
    # Detect anomaly
    result = detector.detect_anomaly(service_id, report_count, response_time)
    
    return result

if __name__ == "__main__":
    # Test the anomaly detection system
    
    # Sample historical data
    historical_data = []
    base_time = datetime.now() - timedelta(days=7)
    
    for i in range(168):  # 7 days of hourly data
        timestamp = base_time + timedelta(hours=i)
        
        # Simulate normal patterns with some noise
        hour = timestamp.hour
        if 9 <= hour <= 17:  # Business hours
            base_reports = 8
            base_response = 180
        else:
            base_reports = 3
            base_response = 120
        
        historical_data.append({
            'timestamp': timestamp.isoformat(),
            'report_count': base_reports + np.random.normal(0, 2),
            'response_time': base_response + np.random.normal(0, 30)
        })
    
    # Test anomaly detection
    test_cases = [
        {'reports': 5, 'response': 150, 'expected': 'normal'},
        {'reports': 25, 'response': 180, 'expected': 'anomaly'},  # High reports
        {'reports': 8, 'response': 500, 'expected': 'anomaly'},   # High response time
        {'reports': 50, 'response': 800, 'expected': 'critical'}, # Both high
    ]
    
    for i, case in enumerate(test_cases):
        result = analyze_service_anomaly(
            service_id=1,
            report_count=case['reports'],
            response_time=case['response'],
            historical_data=historical_data
        )
        
        logger.info(f"Test case {i+1}: Reports={case['reports']}, Response={case['response']}")
        logger.info(f"Result: Anomaly={result['is_anomaly']}, Severity={result['severity']}, Confidence={result['confidence_score']:.2f}")
        logger.info("---")