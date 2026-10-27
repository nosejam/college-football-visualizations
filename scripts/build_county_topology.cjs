// Preserve shared county edges in a compact topology for the offline map.
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const topojson=require(path.join(root,'assets/vendor/topojson-server-3.0.1.min.js'));
const counties=JSON.parse(fs.readFileSync(path.join(root,'data/counties.geojson'),'utf8'));
// Assignment and distance fields belong to the proximity map, not the imperialism basemap.
for(const f of counties.features)f.properties={name:f.properties.name,state:f.properties.state};
const topology=topojson.topology({counties},1e6);
fs.writeFileSync(path.join(root,'data/counties.topojson'),JSON.stringify(topology));
