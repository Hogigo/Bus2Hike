//
//  LocationManager.swift
//  bus2hike
//
//  Created by Antonia Stieger on 30.01.26.
//

import SwiftUI
import MapKit

@Observable
class LocationManager: NSObject, CLLocationManagerDelegate {
   static let shared = LocationManager()
   let manager = CLLocationManager()
   
   override private init() {
      super.init()
      manager.delegate = self
      manager.requestWhenInUseAuthorization()
      manager.desiredAccuracy = kCLLocationAccuracyBest
      manager.distanceFilter = kCLDistanceFilterNone
   }
   
   func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
      if manager.authorizationStatus == .authorizedWhenInUse ||
            manager.authorizationStatus == .authorizedAlways {
         manager.startUpdatingLocation()
      }
   }
}
