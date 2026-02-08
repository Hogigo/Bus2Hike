//
//  MapView.swift
//  bus2hike
//
//  Created by Antonia Stieger on 30.01.26.
//

import SwiftUI
import MapKit

struct MapView: View {
   @StateObject var vm: MapViewModel
   @State var mapCenterCoordinates: CLLocationCoordinate2D?
   
   @State private var stops: [Stop] = []
   
   @Binding var selectedStop: Stop?
   @Binding var selectedHike: Hike?
   
   @Binding var showAllHikes: Bool
   @Binding var showSearchArea: Bool
   @Binding var showDetailCard: Bool
   
   var body: some View {
      ZStack(alignment: .bottomTrailing) {
         
         Map(position: $vm.position) {
            UserAnnotation()
            Stops(for: stops)
            HikingTrails(for: vm.hikes)
         }
         .mapControls {
            MapUserLocationButton()
            MapCompass()
            MapScaleView()
            MapPitchToggle()
         }
         
         if let hike = selectedHike, showDetailCard {
            HikeDetailCard(hike: hike) {
               if let mid = hike.midCoordinate {
                  vm.zoomOut(from: mid)
               }
               selectedHike = nil
            }
            .transition(.move(edge: .bottom))
         }
         
         if showSearchArea {
            SearchAreaButton()
         }
      }
      
      .onMapCameraChange { mapCameraUpdateContext in
         mapCenterCoordinates = mapCameraUpdateContext.camera.centerCoordinate
      }
      .onAppear() {
         mapCenterCoordinates = vm.position.camera?.centerCoordinate
      }
   }
}

extension MapView {
   @MapContentBuilder
   func Stops(for stops: [Stop]) -> some MapContent {
      ForEach(stops) { stop in
         let isSelected = stop.id == selectedStop?.id
         
         Annotation("", coordinate: stop.location) {
            Image(systemName: "bus.fill")
               .resizable()
               .frame(width: isSelected ? 25 : 15, height: isSelected ? 25 : 15)
               .foregroundColor(isSelected ? .white : .white)
               .padding(isSelected ? 10 : 8)
               .background(isSelected ? .selectedBlue : .blue)
               .clipShape(Circle())
               .shadow(radius: 5)
               .overlay(
                  Circle()
                     .stroke(isSelected ? .white : .white, lineWidth: 1)
               )
               .onTapGesture {
                  if selectedStop?.id == stop.id {
                     selectedStop = nil
                     vm.zoomOut(from: stop.location)
                     showAllHikes = false
                  } else {
                     selectedStop = stop
                     vm.zoomIn(on: stop.location)
                  }
               }
         }
      }
   }
   
   @MapContentBuilder
   func HikingTrails(for hikes: [Hike]) -> some MapContent {
      ForEach(hikes) { hike in
         let isSelected = hike.id == selectedHike?.id
         
         MapPolyline(coordinates: hike.coordinates)
            .stroke(isSelected ? .darkRed : .red, lineWidth: 4)
         
         if let mid = hike.midCoordinate {
            Annotation("", coordinate: mid) {
               Image(systemName: "info.circle.fill")
                  .resizable()
                  .frame(width: isSelected ? 20 : 10, height: isSelected ? 20 : 10)
                  .foregroundColor(isSelected ? .white : .white)
                  .padding(isSelected ? 8 : 5)
                  .background(isSelected ? .darkRed : .red)
                  .clipShape(Circle())
                  .shadow(radius: 5)
                  .overlay(
                     Circle()
                        .stroke(isSelected ? .white : .white, lineWidth: 1)
                  )
                  .onTapGesture {
                     if selectedHike?.id == hike.id {
                        showDetailCard = false
                        selectedHike = nil
                        vm.zoomOut(from: vm.regionFor(hike: hike))
                     } else {
                        showDetailCard = true
                        selectedHike = hike
                        vm.zoomIn(on: vm.regionFor(hike: hike))
                     }
                  }
            }
         }
      }
   }
   
   @ViewBuilder
   func SearchAreaButton() -> some View {
      VStack {
         HStack {
            Spacer()
            Button("Search stops in this area") {
               Task {
                  guard let lat = mapCenterCoordinates?.latitude, let lon = mapCenterCoordinates?.longitude else { return }
                  
                  do {
                     stops = try await APIClient.shared.fetchTransportStops(
                        longitude: lon,
                        latitude: lat
                     )
                  } catch {
                     print("Failed to load stops:", error)
                  }
               }
            }
            .padding()
            .background(.inverted, in: Capsule())
            .controlSize(.regular)
            .foregroundStyle(.blue)
            .padding(.top, 8)
            Spacer()
         }
         Spacer()
      }
   }
}
