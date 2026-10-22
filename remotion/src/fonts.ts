import {continueRender, delayRender, staticFile} from 'remotion';

const load = async () => {
  const faces = [
    new FontFace('IBM Plex Sans JP', `url(${staticFile('fonts/IBMPlexSansJP-Bold.ttf')})`, {weight: '700'}),
    new FontFace('IBM Plex Sans JP Semi', `url(${staticFile('fonts/IBMPlexSansJP-SemiBold.ttf')})`, {weight: '600'}),
  ];
  const loaded = await Promise.all(faces.map((f) => f.load()));
  loaded.forEach((f) => document.fonts.add(f));
};

const handle = delayRender('fonts');
load().then(() => continueRender(handle));
