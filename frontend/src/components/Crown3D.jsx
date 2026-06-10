// Photoreal 3D king's crown (Three.js), modeled to match a classic ornate crown:
//  - a strongly FLARED gold band (cup/goblet shape, wider at top)
//  - a smooth polished bottom base + beaded top rim (pearls)
//  - a row of large refractive jewels (ruby/emerald/sapphire/diamond) in gold
//    bezel settings around the band
//  - wide TRIANGULAR peaks rising from the rim, each capped with a gold ball
//    finial and a small gem
// PBR gold + studio reflections (RoomEnvironment), viewed nearly head-on and
// spinning a full 360deg. Rendered to a small transparent canvas behind the
// GOAT card content.
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'

const W = 112
const H = 104

export default function Crown3D() {
  const mountRef = useRef(null)
  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.setSize(W, H)
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.18
    mount.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(32, W / H, 0.1, 100)
    camera.position.set(0, 0.25, 5.2)     // nearly head-on, slightly below
    camera.lookAt(0, 0.4, 0)

    const pmrem = new THREE.PMREMGenerator(renderer)
    const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
    scene.environment = envTex

    const junk = []
    const keep = (x) => { junk.push(x); return x }

    const gold = keep(new THREE.MeshStandardMaterial({ color: 0xffc62e, metalness: 1.0, roughness: 0.18, envMapIntensity: 1.45 }))
    const pearl = keep(new THREE.MeshPhysicalMaterial({
      color: 0xfff6ea, metalness: 0.0, roughness: 0.2, clearcoat: 1, clearcoatRoughness: 0.18,
      iridescence: 0.55, iridescenceIOR: 1.3, envMapIntensity: 1.25,
    }))
    const gemMat = (c) => keep(new THREE.MeshPhysicalMaterial({
      color: c, metalness: 0.0, roughness: 0.05, transmission: 0.92, ior: 2.3, thickness: 0.5,
      attenuationColor: new THREE.Color(c), attenuationDistance: 0.45, envMapIntensity: 1.7, specularIntensity: 1.0,
    }))

    // shared geometries
    const gPearl = keep(new THREE.SphereGeometry(0.05, 16, 16))
    const gFinial = keep(new THREE.SphereGeometry(0.11, 20, 20))
    const gPeak = keep(new THREE.ConeGeometry(0.36, 0.82, 22))      // wide triangular peak
    const gGem = keep(new THREE.IcosahedronGeometry(0.14, 0))
    const gTipGem = keep(new THREE.IcosahedronGeometry(0.06, 0))
    const gBezel = keep(new THREE.TorusGeometry(0.16, 0.03, 14, 28))

    const radiusAtY = (y) => 0.8 + (1.06 - 0.8) * ((y + 0.5) / 1.0)   // flared band radius

    const crown = new THREE.Group()

    // flared band (cup shape) + smooth bottom base + top rim
    crown.add(new THREE.Mesh(keep(new THREE.CylinderGeometry(1.06, 0.8, 1.0, 90, 1, true)), gold))
    const base = new THREE.Mesh(keep(new THREE.TorusGeometry(0.82, 0.1, 24, 90)), gold)
    base.rotation.x = Math.PI / 2; base.position.y = -0.5; crown.add(base)
    const rimTop = new THREE.Mesh(keep(new THREE.TorusGeometry(1.06, 0.05, 22, 96)), gold)
    rimTop.rotation.x = Math.PI / 2; rimTop.position.y = 0.5; crown.add(rimTop)

    // pearl beading along the top edge (just below the peaks)
    const PEARLS = 32
    for (let i = 0; i < PEARLS; i++) {
      const a = (i / PEARLS) * Math.PI * 2, x = Math.cos(a), z = Math.sin(a)
      const p = new THREE.Mesh(gPearl, pearl); p.position.set(x * 1.06, 0.5, z * 1.06); crown.add(p)
    }

    // large jewels in gold bezel settings, around the band middle
    const gemColors = [0xd11a2a, 0xeaf4ff, 0x1aa34a, 0x2a5bd1, 0xd11a2a, 0x1aa34a, 0x2a5bd1, 0xeaf4ff]
    const GEMS = gemColors.length
    for (let i = 0; i < GEMS; i++) {
      const a = (i / GEMS) * Math.PI * 2, x = Math.cos(a), z = Math.sin(a)
      const y = -0.02, r = radiusAtY(y)
      const out = new THREE.Vector3(x * 3, y, z * 3)
      const bezel = new THREE.Mesh(gBezel, gold); bezel.position.set(x * r, y, z * r); bezel.lookAt(out); bezel.scale.set(1.0, 1.3, 1.0); crown.add(bezel)
      const gem = new THREE.Mesh(gGem, gemMat(gemColors[i])); gem.position.set(x * (r + 0.02), y, z * (r + 0.02)); gem.scale.set(1.0, 1.35, 0.6); gem.lookAt(out); crown.add(gem)
    }

    // wide triangular peaks rising from the rim, each with a ball + tip gem
    const PEAKS = 8
    const tipColors = [0xd11a2a, 0x2a5bd1, 0x1aa34a, 0xeaf4ff]
    for (let i = 0; i < PEAKS; i++) {
      const a = ((i + 0.5) / PEAKS) * Math.PI * 2, x = Math.cos(a), z = Math.sin(a)
      const peak = new THREE.Mesh(gPeak, gold); peak.position.set(x * 1.0, 0.9, z * 1.0); crown.add(peak)
      const ball = new THREE.Mesh(gFinial, gold); ball.position.set(x * 1.0, 1.34, z * 1.0); crown.add(ball)
      const tip = new THREE.Mesh(gTipGem, gemMat(tipColors[i % tipColors.length])); tip.position.set(x * 1.0, 1.34, z * 1.06); crown.add(tip)
    }

    crown.rotation.x = -0.04
    scene.add(crown)

    scene.add(new THREE.AmbientLight(0xffffff, 0.22))
    const key = new THREE.DirectionalLight(0xfff2c8, 1.15); key.position.set(2.5, 3, 2.5); scene.add(key)

    let raf
    if (reduce) {
      crown.rotation.y = -0.3
      renderer.render(scene, camera)
    } else {
      const loop = () => { crown.rotation.y += 0.01; renderer.render(scene, camera); raf = requestAnimationFrame(loop) }
      loop()
    }

    return () => {
      if (raf) cancelAnimationFrame(raf)
      envTex.dispose(); pmrem.dispose()
      junk.forEach((d) => d.dispose && d.dispose())
      renderer.dispose()
      const gl = renderer.getContext()
      const lose = gl && gl.getExtension('WEBGL_lose_context')
      if (lose) lose.loseContext()
      if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
  }, [])
  return <div className="crown3d" ref={mountRef} aria-hidden="true" />
}
