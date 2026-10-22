import sharp from 'sharp';
const dir=new URL('.',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1');
for(const [source,target] of [['board.svg','board.png'],['schematic_svg/logger_v2_ups.svg','schematic.png']])await sharp(`${dir}/${source}`,{density:170}).flatten({background:'#ffffff'}).png().toFile(`${dir}/${target}`);
