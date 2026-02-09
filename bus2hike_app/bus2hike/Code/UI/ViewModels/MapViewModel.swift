//
//  MapViewModel.swift
//  bus2hike
//
//  Created by Antonia Stieger on 31.01.26.
//

import MapKit
import Foundation
import SwiftUI
internal import Combine

@MainActor
class MapViewModel: ObservableObject {
   var position: MapCameraPosition = .userLocation(fallback: .automatic)
   
   @Published var stopCoordinates: CLLocationCoordinate2D?
   @Published var radiusKm: Double = 10
   @Published var isLoading = false
   
   @Published var hikes: [Hike] = []
   
   func searchHikes() async {
      guard let coord = stopCoordinates else { return }
      
      isLoading = true
      do {
         // MARK: backend expects lon first!
         hikes = try await APIClient.shared.fetchHikes(
            longitude: coord.longitude,
            latitude: coord.latitude
         )
      } catch {
         print("Hike fetch failed:", error)
      }
      isLoading = false
   }
   
   func captureCoordinates(from stop: Stop) {
      stopCoordinates = stop.location
   }
   
   func captureRadius(from radius: Double) {
      radiusKm = radius
   }
   
   func regionFor(hike: Hike) -> CLLocationCoordinate2D {
      let lats = hike.coordinates.map(\.latitude)
      let lons = hike.coordinates.map(\.longitude)
      
      let minLat = lats.min() ?? 0
      let maxLat = lats.max() ?? 0
      let minLon = lons.min() ?? 0
      let maxLon = lons.max() ?? 0
      
      return CLLocationCoordinate2D(
         latitude: (minLat + maxLat) / 2,
         longitude: (minLon + maxLon) / 2
      )
   }
   
   func zoomIn(on location: CLLocationCoordinate2D) {
      withAnimation(.easeInOut) {
         position = .camera(
            MapCamera(centerCoordinate: location,
                      distance: 6000,
                      heading: 0,
                      pitch: 45)
         )
      }
   }
   
   func zoomOut(from location: CLLocationCoordinate2D) {
      withAnimation(.easeInOut) {
         position = .camera(
            MapCamera(centerCoordinate: location,
                      distance: 15000,
                      heading: 0,
                      pitch: 0)
         )
      }
   }
}

