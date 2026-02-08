//
//  FilterSidebar.swift
//  bus2hike
//
//  Created by Antonia Stieger on 30.01.26.
//

import SwiftUI


struct FilterSidebar: View {
   @StateObject var vm: MapViewModel
   
   @Binding var filters: HikeFilters
   @Binding var showSidebar: Bool
   
   @Binding var selectedStop: Stop?
   @Binding var showAllHikes: Bool
   @Binding var showHikeDetailList: Bool
   
   let onClose: () -> Void
   let onShowAllHikes: () -> Void
   
   var body: some View {
      ZStack {
         
         VStack(alignment: .leading, spacing: 32) {
            
            HStack {
               Text("Filters")
                  .font(.title.bold())
               Spacer()
               Image(systemName: "line.3.horizontal")
                  .bold()
                  .foregroundStyle(.blue)
                  .onTapGesture {
                     withAnimation {
                        showSidebar.toggle()
                     }
                  }
            }
            
            // Bus Stop
            VStack(alignment: .leading) {
               Text("Bus Stop").bold()
               HStack {
                  Image(systemName: selectedStop == nil ? "location.slash" :"mappin")
                  Text(selectedStop?.name ?? "None Selected")
                  Spacer()
                  if selectedStop != nil {
                     Image(systemName: "xmark")
                        .foregroundStyle(.blue)
                        .onTapGesture {
                           onClose()
                        }
                  }
               }
            }
            
            // Radius
            VStack(alignment: .leading) {
               Text("Length of Hike").bold()
               Text("\(Int(filters.radiusKm)) km")
               Slider(value: $filters.radiusKm, in: 1...100, step: 1)
            }
            
            // Difficulty
            VStack(alignment: .leading) {
               Text("Difficulty").bold()
               Picker("Difficulty", selection: $filters.difficulty) {
                  ForEach(Difficulty.allCases) { diff in
                     Text(diff.rawValue).tag(diff)
                  }
               }
               .pickerStyle(.menu)
            }
            
            // Duration
            VStack(alignment: .leading) {
               Text("Duration").bold()
               HStack {
                  DurationField(duration: $filters.maxDuration)
               }
            }
            
            // Circular
            Toggle("Circular only", isOn: $filters.isCircular)
               .tint(.accent)
            
            VStack(alignment: .center, spacing: 18) {
               HStack {
                  Spacer()
                  
                  Button("Search for hikes", systemImage: "magnifyingglass") {
                     guard let stop = selectedStop else { return }
                     
                     vm.captureCoordinates(from: stop)
                     vm.captureRadius(from: filters.radiusKm)
                     
                     Task {
                        await vm.searchHikes()
                     }
                     showAllHikes = true
                  }
                  .disabled(selectedStop == nil)
                  .padding()
                  .background(selectedStop == nil ? .disabled : .blue, in: Capsule())
                  .controlSize(.extraLarge)
                  .foregroundStyle(.white)
                  Spacer()
               }
               .padding(.top, 32)
               
               if showAllHikes {
                  withAnimation {
                     HStack {
                        if !showHikeDetailList {
                           Image(systemName: "chevron.left")
                              .foregroundStyle(.blue)
                        }
                        Text(showHikeDetailList ? "Hide all hikes" : "Show all hikes")
                           .foregroundStyle(.blue)
                        if showHikeDetailList {
                           Image(systemName: "chevron.right")
                              .foregroundStyle(.blue)
                        }
                     }
                     .font(.subheadline)
                     .onTapGesture {
                        showHikeDetailList.toggle()
                        onShowAllHikes()
                     }
                  }
               }
            }
            
            Spacer()
         }
         .padding()
         .frame(width: 300)
         .clipped()
         .background(.ultraThinMaterial)
      }
      .shadow(color: .black.opacity(0.18), radius: 16, x: 8, y: 0)
   }
}
