//
//  APIClient.swift
//  bus2hike
//
//  Created by Antonia Stieger on 30.01.26.
//

import Foundation
import MapKit

final class APIClient {
   static let shared = APIClient()
   private init() {}
   
   let baseURL = URL(string: "http://localhost:8000")!
   
   func fetchHikes(longitude: Double,
                   latitude: Double) async throws -> [Hike] {

       var components = URLComponents(url: baseURL.appendingPathComponent("hikes"),
                                      resolvingAgainstBaseURL: false)!
       components.queryItems = [
           .init(name: "longitude", value: String(longitude)),
           .init(name: "latitude", value: String(latitude)),
           .init(name: "diameter", value: String(1))
       ]

       let url = components.url!
       let (data, _) = try await URLSession.shared.data(from: url)

       let collectionDTO = try JSONDecoder().decode(FeatureCollectionDTO.self, from: data)
       print("Fetched \(collectionDTO.features.count) hikes")

       // Map FeatureDTO to your Hike model
      let hikes = collectionDTO.features.map { feature in
          Hike(
              id: feature.properties.path_id,
              odh_id: "\(feature.properties.path_id)",

              name: feature.properties.name,
              description: feature.properties.description,

              difficulty: "Easy",
              length_km: feature.properties.total_distance_km,
              duration_minutes: 150,
              elevation_gain_m: 420,
              elevation_loss_m: 420,
              circular: true,
              coordinates: feature.geometry.coordinates.map {
                  CLLocationCoordinate2D(latitude: $0[1], longitude: $0[0])
              }
          )
      }
       return hikes
   }
   
   func fetchTransportStops(longitude: Double,
                            latitude: Double) async throws -> [Stop] {
       var components = URLComponents(url: baseURL.appendingPathComponent("transport-stops"),
                                      resolvingAgainstBaseURL: false)!
       components.queryItems = [
           .init(name: "longitude", value: String(longitude)),
           .init(name: "latitude", value: String(latitude)),
           .init(name: "range_km", value: String(2))
       ]

       let url = components.url!
       let (data, _) = try await URLSession.shared.data(from: url)
       let dtos = try JSONDecoder().decode([StopDTO].self, from: data)
       return dtos.map(Stop.init)
   }

}
