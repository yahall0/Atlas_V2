/**
 * Demo mindmaps — one per case category emitted by the FIR classifier.
 *
 * Used by `useMindmap` as a *fallback* when the backend has no real
 * mindmap stored for the FIR yet. Lets the demo flow show a populated
 * mindmap immediately after FIR classification, without waiting for
 * the KB-driven generator to be wired to the deployed instance.
 *
 * Structure (radial, center-hub):
 *
 *                       ⚖️ Applicable BNS Sections
 *                                    │
 *      ⚠️ Common FIR Gaps  ──  FIR {number} | {category}  ──  🚨 Immediate Actions
 *                                    │
 *                       📋 Panchnama   🔬 Evidence   🩸 Forensics
 *                              💬 Witness Bayan   🛡️ Procedural Safeguards
 *
 * Each leaf preserves a `kb_layer` hint in metadata so colour-banding by
 * authority (statute / SOP / case-law) still works when the backend
 * later replaces this with a KB-driven mindmap.
 */

import type {
  MindmapData,
  MindmapNode,
  NodePriority,
  NodeType,
} from './nodes/types';

// ─── Branch slot definitions (ordered, with emoji + node_type binding) ─────

type LayerHint =
  | 'canonical_legal'
  | 'investigation_playbook'
  | 'case_law_intelligence';

type BranchSlot =
  | 'bns'
  | 'immediate'
  | 'panchnama'
  | 'evidence'
  | 'forensics'
  | 'bayan'
  | 'safeguards'
  | 'gaps';

interface SlotMeta {
  title: string;
  node_type: NodeType;
  layer: LayerHint;
}

// Emoji glyphs are stored as Unicode escape sequences so auto-formatters /
// linters that aggressively strip non-ASCII characters can't silently
// break the branch labels. Keyed by BranchSlot so SLOTS stays pure data.
const SLOT_EMOJI: Record<BranchSlot, string> = {
  bns:        '\u2696\uFE0F',         
  immediate:  '\u{1F6A8}',            
  panchnama:  '\u{1F4CB}',            
  evidence:   '\u{1F52C}',            
  forensics:  '\u{1FA78}',            
  bayan:      '\u{1F4AC}',            
  safeguards: '\u{1F6E1}\uFE0F',      
  gaps:       '\u26A0\uFE0F',         
};

const SLOTS: Record<BranchSlot, SlotMeta> = {
  bns:        { title: 'Applicable BNS Sections', node_type: 'legal_section',    layer: 'canonical_legal' },
  immediate:  { title: 'Immediate Actions',       node_type: 'immediate_action', layer: 'investigation_playbook' },
  panchnama:  { title: 'Panchnama',               node_type: 'panchnama',        layer: 'investigation_playbook' },
  evidence:   { title: 'Evidence Collection',     node_type: 'evidence',         layer: 'investigation_playbook' },
  forensics:  { title: 'Blood / DNA Forensics',   node_type: 'forensic',         layer: 'investigation_playbook' },
  bayan:      { title: 'Witness Bayan',           node_type: 'witness_bayan',    layer: 'investigation_playbook' },
  safeguards: { title: 'Procedural Safeguards',   node_type: 'evidence',         layer: 'investigation_playbook' },
  gaps:       { title: 'Common FIR Gaps',         node_type: 'gap_from_fir',     layer: 'case_law_intelligence' },
};

// Display order of primary branches around the hub (clockwise from top).
const SLOT_ORDER: BranchSlot[] = [
  'bns', 'immediate', 'panchnama', 'evidence',
  'forensics', 'bayan', 'safeguards', 'gaps',
];

// ─── Per-leaf spec ─────────────────────────────────────────────────────────

interface LeafSpec {
  title: string;
  description: string;
  priority?: NodePriority;
  bns_section?: string;
  ipc_section?: string;
  crpc_section?: string;
}

/** Per-category content — only the slots that have items appear as branches. */
type CategoryContent = Partial<Record<BranchSlot, LeafSpec[]>>;

// ─── Reusable building blocks ──────────────────────────────────────────────

const COMMON_SAFEGUARDS: LeafSpec[] = [
  {
    title: 'Arrest under D.K. Basu + BNSS S.35 / 36 / 187',
    description:
      'Arrest memo with witness signature, intimation to relative, medical examination at arrest, production before Magistrate within 24 h, no female arrest after sunset without written Magistrate order.',
    priority: 'critical',
  },
  {
    title: 'Right to legal aid — BNSS S.36(d) + Article 39A',
    description:
      'Inform accused of right to counsel of choice and free legal aid via DLSA if indigent. Record acknowledgment in case diary.',
    priority: 'recommended',
  },
];

const COMMON_BSA63: LeafSpec = {
  title: 'BSA S.63 — Electronic Evidence Certificate',
  description:
    'Mandatory pre-condition for admissibility of CCTV, CDR, mobile extracts, dump data. Must come from the person in control of the originating device, dated at the time of seizure, with SHA-256 hash of the original media noted on the certificate.',
  priority: 'critical',
};

// ─── Per-category content ──────────────────────────────────────────────────

const MURDER: CategoryContent = {
  bns: [
    {
      title: 'BNS S.103 — Murder',
      description:
        'Death or imprisonment for life, and fine. Five exceptions (provocation, private defence, public servant, sudden fight, consent).',
      priority: 'critical',
      bns_section: '103',
      ipc_section: '302',
    },
    {
      title: 'BNS S.105 — Culpable Homicide',
      description:
        'Alternative when act falls under a S.103 exception or is done with knowledge but without intention. Part I: life or up to 10 y; Part II: up to 10 y.',
      priority: 'critical',
      bns_section: '105',
      ipc_section: '304',
    },
    {
      title: 'BNSS S.194 — Inquest by Police',
      description:
        'Two independent panchas at scene; record cause of death, body position, weapons, articles. Body not removed without inquest.',
      priority: 'critical',
      crpc_section: '174',
    },
    {
      title: 'BNSS S.176 — Magisterial Inquiry',
      description:
        'Mandatory Judicial Magistrate inquiry for deaths in custody / within 7 y of marriage in suspicious circumstances / unknown cause.',
      priority: 'recommended',
    },
    COMMON_BSA63,
  ],
  immediate: [
    {
      title: 'Secure the crime scene',
      description:
        'Cordon, inner + outer perimeter, scene entry log, no article touched. Tarpaulin overhead if outdoor and weather threatens, without disturbing evidence below.',
      priority: 'critical',
    },
    {
      title: 'Register FIR under BNSS S.173',
      description:
        'Verbatim record, free copy to informant, electronic registration permitted. Zero FIR if outside jurisdiction — transfer within 24 h.',
      priority: 'critical',
    },
    {
      title: 'Inform Magistrate, arrange post-mortem',
      description:
        'PM at nearest government hospital, preferably two medical officers. Videography mandatory for 7+ year offences (BNSS S.194).',
      priority: 'critical',
    },
    {
      title: 'Conduct inquest panchnama at scene',
      description:
        'Two independent panchas, record cause of death, body position, injuries, weapons, surrounding circumstances — defects compound.',
      priority: 'critical',
    },
  ],
  panchnama: [
    {
      title: 'Spot panchnama (scene of crime)',
      description:
        'GPS coordinates, condition of doors / windows / lights, body posture, rigor / lividity, bloodstain locations and patterns, weapon at scene, signs of struggle, scaled sketch.',
      priority: 'critical',
    },
    {
      title: 'Seizure panchnama (zimma)',
      description:
        'Each item exhibit-numbered, sealed in tamper-evident container, signed across seal by panchas + IO. BNSS S.105.',
      priority: 'critical',
    },
    {
      title: 'Recovery / discovery panchnama (BSA S.8)',
      description:
        'Accused voluntarily points out — only the discovered fact admissible. Panchas witness actual pointing out; video the entire walk from vehicle to recovery point.',
      priority: 'critical',
    },
    {
      title: 'Independent pancha standard',
      description:
        'Both panchas independent of station, locality residents, adult with verifiable ID, mobile + relative\'s mobile recorded.',
      priority: 'recommended',
    },
  ],
  evidence: [
    {
      title: 'Post-mortem report',
      description:
        'Cause of death, time of death, ante- vs post-mortem injuries, dimensions of each wound, viscera preserved, weapon-wound consistency opinion.',
      priority: 'critical',
    },
    {
      title: 'Weapon recovery + FSL matching',
      description:
        'Recovery via discovery (BSA S.8) or independent search. Sealed in pancha presence, sent to FSL for blade-wound dimension or test-fire matching.',
      priority: 'critical',
    },
    {
      title: 'CCTV + electronic surveillance',
      description:
        'Seize within hours — overwritten in 7-30 days. CDR + tower-dump via BNSS S.94. SHA-256 hash original media at seizure.',
      priority: 'critical',
    },
    {
      title: 'Call Detail Records (CDR + IPDR)',
      description:
        'Communication timeline of accused and victim covering 7-15 days around the incident. Cell tower hits to corroborate / rebut alibi.',
      priority: 'recommended',
    },
  ],
  forensics: [
    {
      title: 'Blood-stain collection — 6 sample rule',
      description:
        'Wet swab per stain, dry swab control, substrate cutting, deceased reference (EDTA 5 ml at PM), suspect reference (BNSS S.349 if refused), negative control. Paper envelopes, never plastic.',
      priority: 'critical',
    },
    {
      title: 'Cold-chain — 4 °C in 4 h, FSL in 72 h',
      description:
        'Beyond 72 h ambient, STR success drops <60%. Ice-pack cooler in SOC vehicle. Photograph cold-bag thermometer at handover and FSL receipt.',
      priority: 'critical',
    },
    {
      title: 'DNA STR profiling',
      description:
        'Compare scene / victim / accused profiles. Mukesh v. State (NCT Delhi) (2017) 6 SCC 1 — DNA reliable when chain of custody maintained.',
      priority: 'critical',
    },
    {
      title: 'BPA photograph protocol',
      description:
        'Establishing → mid-range → close-up perpendicular with ABFO No. 2 scale. Convergence sketch in situ. RAW + JPEG. SHA-256 the SD card before download.',
      priority: 'recommended',
    },
  ],
  bayan: [
    {
      title: 'Eyewitness bayan — BNSS S.180',
      description:
        'Verbatim, vernacular (Gujarati), same-day. Read back to witness, note read-back. Position, distance, lighting, duration, sequence of events.',
      priority: 'critical',
    },
    {
      title: 'Last-seen witnesses',
      description:
        'Persons who last saw deceased alive, especially with accused. Last-seen-together doctrine shifts burden if time-gap is short. Corroborate with CDR + CCTV.',
      priority: 'critical',
    },
    {
      title: 'BNSS S.183 statement before Magistrate',
      description:
        'Critical and likely-hostile witnesses examined on oath before Judicial Magistrate. Substantive evidence. Apply early — do not wait for trial-stage hostility.',
      priority: 'critical',
    },
  ],
  safeguards: COMMON_SAFEGUARDS,
  gaps: [
    {
      title: 'Delay in FIR registration without recorded explanation',
      description:
        'Sharad Birdhichand (1984) 4 SCC 116 + Thulia Kali (1973) 1 SCC 9 — unexplained delay is a fatal infirmity. Record contemporaneous reason in case diary.',
      priority: 'critical',
    },
    {
      title: 'Pre-dictated discovery panchnama',
      description:
        'Pulukuri Kotayya line + GHC Adam Hajibhai (2019) — recovery location recorded before pointing out collapses BSA S.8 admissibility.',
      priority: 'critical',
    },
    {
      title: 'Missing BSA S.63 certificate at seizure',
      description:
        'Anvar P.V. (2014) 10 SCC 473 + Arjun Panditrao (2020) 7 SCC 1 — certificate from device controller, dated at seizure, with SHA-256 hash. Trial-stage afterthought is fatal.',
      priority: 'critical',
    },
    {
      title: 'No S.183 BNSS statement of exposed witness',
      description:
        'Family of accused, weak village witnesses turn hostile at trial. Identify in week 1 and apply for S.183 examination before Magistrate.',
      priority: 'recommended',
    },
  ],
};

const THEFT: CategoryContent = {
  bns: [
    {
      title: 'BNS S.303 — Theft',
      description:
        'Dishonestly moving any movable property out of possession without consent. Up to 3 y and / or fine.',
      priority: 'critical',
      bns_section: '303',
      ipc_section: '378',
    },
    {
      title: 'BNS S.305 — Aggravated theft (dwelling / vehicle)',
      description:
        'Theft in any building used as a dwelling, place of worship, or for custody of property — up to 7 y and fine.',
      priority: 'critical',
      bns_section: '305',
    },
    {
      title: 'BNS S.317 — Receiving stolen property',
      description:
        'Whoever dishonestly receives or retains stolen property knowing it is stolen — up to 3 y and fine. Triggers parallel investigation against receiver chain.',
      priority: 'recommended',
      bns_section: '317',
    },
    COMMON_BSA63,
  ],
  immediate: [
    {
      title: 'Seal and photograph point of entry / exit',
      description:
        'Photograph from outside-in and inside-out before any cleaning. Lift latent prints from broken glass, door handles, pried surfaces. Tool-mark direction and depth.',
      priority: 'critical',
    },
    {
      title: 'Inventory of stolen property',
      description:
        'Detailed list with descriptions, model + serial numbers, photographs, IMEI for phones, VIN for vehicles. Circulate to nearby stations and pawn-shop circles.',
      priority: 'critical',
    },
    {
      title: 'Seize CCTV from scene + approach roads',
      description:
        'Footage typically overwritten 7-30 days. Cameras at scene, on access roads, at exit points (highway tolls, ATMs). BSA S.63 certificate at seizure.',
      priority: 'critical',
    },
  ],
  panchnama: [
    {
      title: 'Spot panchnama with point-of-entry detail',
      description:
        'Method of entry (lock break, ladder, vent), tool used, direction of force, items disturbed. Sketch with scale showing approach + escape routes.',
      priority: 'critical',
    },
    {
      title: 'Recovery panchnama (BSA S.8) for stolen articles',
      description:
        'Accused voluntarily leads to recovery. Panchas witness actual pointing out, photograph article in situ before lifting, match against complainant\'s inventory.',
      priority: 'critical',
    },
  ],
  evidence: [
    {
      title: 'Latent fingerprints from POE + handled surfaces',
      description:
        'Powder lift on smooth surfaces, ninhydrin on paper, cyanoacrylate fuming on plastic. Photograph before lifting. AFIS search if no suspect.',
      priority: 'critical',
    },
    {
      title: 'Tool-mark casts and footwear impressions',
      description:
        'Silicone or dental-stone casting of tool marks at POE. Photograph footprints with scale; cast in plaster. Match against tools / shoes recovered from accused.',
      priority: 'recommended',
    },
    {
      title: 'CCTV chain — scene → road → onward',
      description:
        'Plot accused movement across multiple cameras. Hash each clip, BSA S.63 certificate per camera operator.',
      priority: 'critical',
    },
  ],
  forensics: [
    {
      title: 'Fingerprint comparison report',
      description:
        'Submit lifted prints + accused\'s chance prints to Fingerprint Bureau. Expert opinion required for court. Maintain chain of custody.',
      priority: 'recommended',
    },
  ],
  bayan: [
    {
      title: 'Complainant bayan with full inventory',
      description:
        'Verbatim list of stolen items with proof of ownership (purchase invoices, photographs, insurance schedules). Last verified time of property in possession.',
      priority: 'critical',
    },
    {
      title: 'Neighbour / watchman bayans',
      description:
        'Persons in vicinity at relevant time, vehicle / person observations, unusual sounds. Lighting and visibility from witness position.',
      priority: 'recommended',
    },
  ],
  safeguards: COMMON_SAFEGUARDS,
  gaps: [
    {
      title: 'Recovery without independent pancha',
      description:
        'Pawn-shop owner is not an independent pancha for a recovery from his shop. Earabhadrappa v. Karnataka (1983) 2 SCC 330 — recent + exclusive possession presumption collapses with defective recovery.',
      priority: 'critical',
    },
    {
      title: 'Owner failed to identify with distinguishing marks',
      description:
        'Mere recovery insufficient — owner must identify with reference to distinguishing marks. Photograph article alongside owner\'s purchase records during identification panchnama.',
      priority: 'recommended',
    },
  ],
};

const RAPE: CategoryContent = {
  bns: [
    {
      title: 'BNS S.64 — Rape',
      description:
        'RI not less than 10 y, extendable to life, and fine. Aggravated forms (S.64(2), S.65, S.66) attract higher minimums up to death in rarest cases.',
      priority: 'critical',
      bns_section: '64',
      ipc_section: '376',
    },
    {
      title: 'BNSS S.183 — Statement before Magistrate',
      description:
        'Recorded in victim\'s language, audio-video where feasible. Substantive evidence. No police officer present.',
      priority: 'critical',
    },
    {
      title: 'BNSS S.176(1)(a) — Woman recorder',
      description:
        'Statement under S.180 BNSS shall be recorded by a woman police officer. Failure is a defence point.',
      priority: 'critical',
    },
    {
      title: 'POCSO Act if victim under 18',
      description:
        'POCSO provisions override and apply concurrently. Mandatory reporting under S.19; statement under S.25 by Magistrate.',
      priority: 'critical',
    },
  ],
  immediate: [
    {
      title: 'Medical examination within 24 h',
      description:
        'Government hospital, woman doctor where available. Two-finger test prohibited (Lillu v. Haryana). Vaginal swabs, pubic hair combings, fingernail scrapings, clothing.',
      priority: 'critical',
    },
    {
      title: 'BNSS S.183 statement before Magistrate ASAP',
      description:
        'Audio-video where feasible. Victim\'s language. No police officer present during recording.',
      priority: 'critical',
    },
    {
      title: 'Preserve scene, victim\'s clothing, bedding',
      description:
        'Each item in separate paper bag, sealed in pancha presence. Cold-chain for biological samples.',
      priority: 'critical',
    },
  ],
  panchnama: [
    {
      title: 'Spot panchnama (location of offence)',
      description:
        'Rough sketch, lighting, accessibility, signs of struggle. Two woman panchas where possible.',
      priority: 'critical',
    },
    {
      title: 'Seizure panchnama for clothing + biological exhibits',
      description:
        'Each item individually packaged in paper, sealed, signed across seal. Refrigerated transport to FSL.',
      priority: 'critical',
    },
  ],
  evidence: [
    {
      title: 'Medical examination report (FSL form)',
      description:
        'Findings on injuries (genital + extragenital), age estimation if minor, mental capacity for consent. Two-finger test prohibited.',
      priority: 'critical',
    },
  ],
  forensics: [
    {
      title: 'DNA profiling — STR comparison',
      description:
        'Compare victim swabs, accused reference, scene articles. Cold-chain mandatory.',
      priority: 'critical',
    },
  ],
  bayan: [
    {
      title: 'Victim bayan in safe environment',
      description:
        'Woman officer, supportive setting (victim\'s residence or DLSA centre), verbatim, no leading questions.',
      priority: 'critical',
    },
    {
      title: 'Family + first-disclosed-to witnesses',
      description:
        'Persons to whom victim first disclosed the offence — admissible as res gestae if soon after. Record context, language used, time elapsed.',
      priority: 'critical',
    },
  ],
  safeguards: [
    {
      title: 'Identity protection — BNSS S.72',
      description:
        'Victim identity not disclosed in any record / order / judgment. Print + electronic media restraint under S.72(2). Anonymisation in chargesheet.',
      priority: 'critical',
    },
    {
      title: 'In-camera trial — BNSS S.366',
      description:
        'Trial in-camera at victim\'s instance. Recording with screen / video link. Compensation under Victim Compensation Scheme.',
      priority: 'recommended',
    },
  ],
  gaps: [
    {
      title: 'Two-finger test recorded in MER',
      description:
        'Lillu v. State of Haryana (2013) 14 SCC 643 — two-finger test inadmissible and violates dignity. Excise from MER and use objective markers.',
      priority: 'critical',
    },
    {
      title: 'Delay in FIR not contextualised',
      description:
        'Karnel Singh v. M.P. (1995) 5 SCC 518 — delay in sexual offences expected; trauma + stigma are themselves explanation. Record contemporaneous reasons.',
      priority: 'recommended',
    },
  ],
};

const CYBER: CategoryContent = {
  bns: [
    {
      title: 'IT Act S.66 — Computer-related offences',
      description:
        'Dishonestly or fraudulently doing any S.43 act — up to 3 y and / or fine ₹5 lakh. Companion BNS S.318 (cheating) routinely added.',
      priority: 'critical',
    },
    {
      title: 'IT Act S.66C / S.66D — Identity / cheating by personation',
      description:
        'S.66C identity theft — up to 3 y + ₹1 lakh. S.66D personation via computer resource — up to 3 y + ₹1 lakh.',
      priority: 'critical',
    },
    {
      title: 'BNS S.318 — Cheating',
      description:
        'Up to 7 y and fine. Predicate offence in most online fraud cases.',
      priority: 'critical',
      bns_section: '318',
      ipc_section: '420',
    },
    COMMON_BSA63,
  ],
  immediate: [
    {
      title: 'Freeze suspect accounts via NCRP / 1930',
      description:
        'Report on cybercrime.gov.in within golden hour (24 h). 1930 helpline triggers bank-level freeze on transferred funds.',
      priority: 'critical',
    },
    {
      title: 'Preserve victim\'s device + screenshots',
      description:
        'Do not factory-reset. Forensic image (write-blocker), preserve chats, transaction SMS, app screenshots. Hash original media.',
      priority: 'critical',
    },
    {
      title: 'BNSS S.94 notice to platforms',
      description:
        'To bank, payment gateway, telecom, social media — for KYC, transaction logs, IP logs, device fingerprints. Mention exact log fields and date range.',
      priority: 'critical',
    },
  ],
  panchnama: [
    {
      title: 'Seizure panchnama for victim + accused devices',
      description:
        'Each device individually sealed in tamper-evident bag. Note IMEI, serial, screen state. Chain of custody from seizure to FSL.',
      priority: 'critical',
    },
  ],
  evidence: [
    {
      title: 'Bank statement chain — victim → mule → final',
      description:
        'Trace funds across 3-5 hops. Identify mule accounts (often students, daily-wage). KYC documents, login IPs, device IDs from each hop bank.',
      priority: 'critical',
    },
    {
      title: 'IP + device fingerprint correlation',
      description:
        'Same device ID / IP across mule accounts links them. Cross-reference with telecom CDR for the period.',
      priority: 'critical',
    },
    {
      title: 'Wallet / UPI VPA history',
      description:
        'NPCI requisition for VPA holder details and transaction history. Bank-issued UPI handle resolves to underlying account.',
      priority: 'recommended',
    },
  ],
  forensics: [
    {
      title: 'Mobile / laptop forensic image (write-blocker)',
      description:
        'Forensic image of accused devices using write-blocker. Cellebrite / FTK extraction. SHA-256 hash of image and source. BSA S.63 certificate.',
      priority: 'critical',
    },
    {
      title: 'Recovered chats + cloud account exports',
      description:
        'WhatsApp business chats, Telegram exports, cloud backups (Google Takeout, iCloud) under S.94 BNSS notice.',
      priority: 'recommended',
    },
  ],
  bayan: [
    {
      title: 'Victim bayan with timeline reconstruction',
      description:
        'Detailed timeline: source of contact, modus, transaction sequence, communication channel. Attach screenshots numbered and authenticated.',
      priority: 'critical',
    },
    {
      title: 'Bank nodal officer — S.63 BSA certificate',
      description:
        'Certificate from bank nodal officer (not IO) for each transaction log produced. Same for telecom CDR.',
      priority: 'critical',
    },
  ],
  safeguards: COMMON_SAFEGUARDS,
  gaps: [
    {
      title: 'S.63 BSA certificate signed by IO instead of device controller',
      description:
        'Anvar P.V. + Arjun Panditrao — certificate must come from person in control of originating device. IO-signed certificate is fatal.',
      priority: 'critical',
    },
    {
      title: 'Mule account complicity not evidenced',
      description:
        'Receiver of funds — proof of knowledge required, mere receipt insufficient. Bank statement + KYC + linked devices needed for charge under BNS S.317.',
      priority: 'critical',
    },
  ],
};

const ACCIDENT: CategoryContent = {
  bns: [
    {
      title: 'BNS S.106 — Death by negligent act',
      description:
        'Causing death by rash / negligent act not amounting to culpable homicide. Up to 5 y and fine; medical professionals — special provisions.',
      priority: 'critical',
      bns_section: '106',
      ipc_section: '304A',
    },
    {
      title: 'BNS S.281 — Rash driving on public way',
      description:
        'Rash or negligent driving so as to endanger human life — up to 6 m or fine ₹1000. Companion charge with S.106 in fatal RTAs.',
      priority: 'critical',
      bns_section: '281',
      ipc_section: '279',
    },
    {
      title: 'Motor Vehicles Act S.184 / 185 / 187',
      description:
        'Dangerous driving (S.184), drunken driving (S.185), failure to stop after accident (S.187). MV Act runs parallel.',
      priority: 'recommended',
    },
  ],
  immediate: [
    {
      title: 'Scene photographs before vehicles moved',
      description:
        'Vehicle positions, skid marks, debris field, damage angles, traffic signals state. Establish point of impact from debris pattern.',
      priority: 'critical',
    },
    {
      title: 'Driver medical — alcohol / drug screening',
      description:
        'Within 4 h. Breath analyser at scene; blood sample at hospital (EDTA + fluoride for alcohol). FSL within 72 h.',
      priority: 'critical',
    },
    {
      title: 'Inquest under BNSS S.194 (if fatal)',
      description:
        'Two independent panchas, body position, injuries, vehicle involved, road conditions, weather. Photograph body in situ before removal.',
      priority: 'critical',
    },
  ],
  panchnama: [
    {
      title: 'Spot panchnama with scaled sketch',
      description:
        'Road width, lane markings, traffic signals, signage, gradient, view obstructions. Skid-mark length and direction. Fixed-reference measurements.',
      priority: 'critical',
    },
    {
      title: 'Seizure of both vehicles',
      description:
        'Vehicle seized as case property. Mechanical inspection by RTO / MVI for brake / steering / tyre. Photograph odometer and damage extent.',
      priority: 'critical',
    },
  ],
  evidence: [
    {
      title: 'CCTV / dashcam from scene + approach',
      description:
        'Highway tolls, traffic-signal cameras, nearby shops / petrol pumps, dashcams of bystander vehicles. Within hours — overwritten quickly.',
      priority: 'critical',
    },
    {
      title: 'Mechanical inspection report (MVI)',
      description:
        'RTO MVI certifies brake function, steering, tyre tread, lights, horn. Establishes contributory mechanical failure or rules it out.',
      priority: 'critical',
    },
    {
      title: 'Post-mortem with cause-of-death link',
      description:
        'PM links injuries to crash mechanics — head trauma, internal hemorrhage, crush injuries. Toxicology on driver if available.',
      priority: 'critical',
    },
  ],
  bayan: [
    {
      title: 'Eyewitness bayans — multiple positions',
      description:
        'Witnesses from different vantage points (oncoming, behind, pedestrian). Lighting, weather, vehicle speed estimate, signal state.',
      priority: 'critical',
    },
    {
      title: 'Driver bayan — sequence + reaction',
      description:
        'Speed, lane, last action before impact, reason for failure to avoid. Recorded after medical screening, not before.',
      priority: 'recommended',
    },
  ],
  safeguards: COMMON_SAFEGUARDS,
  gaps: [
    {
      title: 'Speed not proved by skid-mark calculation',
      description:
        'Skid-mark length × surface coefficient establishes speed. Without measured skid + surface analysis, speed allegations are weak.',
      priority: 'recommended',
    },
    {
      title: 'Driver not gross-negligence-proved (Jacob Mathew)',
      description:
        'Jacob Mathew v. Punjab (2005) 6 SCC 1 — negligence must be gross and culpable, not mere error of judgment. Demonstrate departure from standard of ordinary care.',
      priority: 'critical',
    },
  ],
};

const DOWRY: CategoryContent = {
  bns: [
    {
      title: 'BNS S.80 — Dowry death',
      description:
        'Death within 7 y of marriage by burns / injury / abnormal circumstances + cruelty for dowry — minimum 7 y, extendable to life. BSA S.118 presumption.',
      priority: 'critical',
      bns_section: '80',
      ipc_section: '304B',
    },
    {
      title: 'BNS S.85 / S.86 — Cruelty by husband or relatives',
      description:
        'Willful conduct likely to drive woman to suicide or cause grave injury, or harassment to coerce dowry. Up to 3 y + fine.',
      priority: 'critical',
      bns_section: '85',
      ipc_section: '498A',
    },
    {
      title: 'Dowry Prohibition Act S.3 / 4',
      description:
        'Giving / taking / demanding dowry. Companion charges under DP Act run parallel.',
      priority: 'recommended',
    },
  ],
  immediate: [
    {
      title: 'Mandatory Magisterial inquiry — BNSS S.176',
      description:
        'Death within 7 y of marriage in suspicious circumstances triggers mandatory Judicial Magistrate inquiry. Inform Magistrate within hours.',
      priority: 'critical',
    },
    {
      title: 'Inquest at scene + PM with viscera preservation',
      description:
        'Two panchas at scene, photograph body in situ, note position, burns extent, ligature marks. PM with viscera for toxicology.',
      priority: 'critical',
    },
    {
      title: 'Seize matrimonial home articles',
      description:
        'Letters, diaries, gifts, jewellery, financial records. Photograph kitchen if burn case. Preserve any container / fluid for chemical analysis.',
      priority: 'critical',
    },
  ],
  panchnama: [
    {
      title: 'Spot panchnama at matrimonial home',
      description:
        'Sketch with kitchen layout if burn case, ligature points if hanging, pesticide containers if poisoning. Two panchas, one woman where possible.',
      priority: 'critical',
    },
  ],
  evidence: [
    {
      title: 'Communication trail — calls, messages, photos',
      description:
        'Pattern of dowry demands. Phone records of accused household, screenshots from victim\'s phone, social-media DMs.',
      priority: 'recommended',
    },
  ],
  forensics: [
    {
      title: 'Toxicology + chemical analysis',
      description:
        'Viscera for poison, kitchen residues for accelerant in burn cases, container swabs. Preserve in saturated salt or rectified spirit; FSL within 72 h.',
      priority: 'critical',
    },
  ],
  bayan: [
    {
      title: 'Natal family bayans',
      description:
        'Parents, siblings of deceased. Pattern of complaints, dowry demands, recent calls / messages. Documents — gift lists, photographs, receipts.',
      priority: 'critical',
    },
    {
      title: 'Dying declaration if available',
      description:
        'If victim survived even briefly — dying declaration before Magistrate is highest evidence (BSA S.26). Audio-video where feasible.',
      priority: 'critical',
    },
    {
      title: 'Neighbours of matrimonial home',
      description:
        'Pattern of quarrels, visible injuries, victim\'s state at last sighting. Independent of both families.',
      priority: 'recommended',
    },
  ],
  safeguards: COMMON_SAFEGUARDS,
  gaps: [
    {
      title: 'Cruelty without proximate dowry-nexus',
      description:
        'Hira Lal v. State (NCT Delhi) (2003) 8 SCC 80 — cruelty must be "soon before death" with dowry connection. Stale demands without proximate harassment fail S.80.',
      priority: 'critical',
    },
    {
      title: 'BSA S.118 presumption not rebutted by alternate explanation',
      description:
        'Defence may rebut presumption — investigation must close all alternative explanations (suicide, accident, natural cause).',
      priority: 'recommended',
    },
  ],
};

const MISSING: CategoryContent = {
  bns: [
    {
      title: 'BNSS S.359 — Search for missing persons',
      description:
        'Power to enter and search any place where missing person believed to be. Zero FIR applicable; cross-jurisdictional follow-up mandatory.',
      priority: 'critical',
    },
    {
      title: 'BNS S.137 — Kidnapping (if minor or coercion suspected)',
      description:
        'Kidnapping from lawful guardianship of minor under 18 (girl) / 16 (boy). Add at the moment evidence of coercion or removal emerges.',
      priority: 'recommended',
      bns_section: '137',
      ipc_section: '363',
    },
  ],
  immediate: [
    {
      title: 'Register on Khoya-Paya / NCRB Missing Persons Portal',
      description:
        'Within hours. Photograph + biometrics + descriptors. Cross-circulate to all stations and railway / airport units.',
      priority: 'critical',
    },
    {
      title: 'CDR + last-tower of mobile',
      description:
        'BNSS S.94 notice to telecom — last 7-15 days CDR / IPDR + tower-dump near last-known location. Plot trajectory.',
      priority: 'critical',
    },
    {
      title: 'CCTV from last-known location outwards',
      description:
        'Bus stand, railway station, highway tolls, ATM cameras. Plot person\'s movement across cameras.',
      priority: 'critical',
    },
  ],
  panchnama: [
    {
      title: 'Search panchnama at residence + last-known location',
      description:
        'Two panchas, exact items missing (clothes, ID documents, money, phone), state of room as found. Sketch.',
      priority: 'recommended',
    },
  ],
  evidence: [
    {
      title: 'Bank + UPI activity since disappearance',
      description:
        'Any transaction post-disappearance is a strong signal. BNSS S.94 to banks + NPCI for UPI VPA activity.',
      priority: 'recommended',
    },
  ],
  bayan: [
    {
      title: 'Family + close-circle bayans',
      description:
        'State of mind, recent disputes, financial pressure, romantic involvement. Phone usage pattern, social-media activity.',
      priority: 'critical',
    },
    {
      title: 'Last-seen witnesses',
      description:
        'Persons who last saw the missing person, time, place, companions, demeanour, direction of travel.',
      priority: 'critical',
    },
  ],
  safeguards: COMMON_SAFEGUARDS,
  gaps: [
    {
      title: 'No conversion to murder case workflow if body found',
      description:
        'If missing person\'s body is later found, the existing investigation (CDR, CCTV, last-seen) becomes the foundation for murder charge. Treat missing as a pre-murder investigation.',
      priority: 'recommended',
    },
  ],
};

const NDPS: CategoryContent = {
  bns: [
    {
      title: 'NDPS Act S.20 / 21 / 22 — Possession',
      description:
        'Quantity-based punishment: small (RI up to 1 y), commercial (10-20 y + ₹1-2 lakh). Trigger BNSS S.187 special remand provisions.',
      priority: 'critical',
    },
    {
      title: 'NDPS Act S.50 — Personal search safeguard',
      description:
        'Person to be searched must be informed of right to be searched before Gazetted Officer or Magistrate. Failure renders recovery inadmissible (Vijaysinh Chandubha Jadeja).',
      priority: 'critical',
    },
    {
      title: 'NDPS Act S.42 — Authority to enter and search',
      description:
        'Empowered officer must record grounds of belief in writing before search. Failure to record is a fatal infirmity.',
      priority: 'critical',
    },
  ],
  immediate: [
    {
      title: 'Pre-search S.50 NDPS notice in writing',
      description:
        'Written notice to suspect of right under S.50 before any search. Two independent panchas, signed by suspect + panchas + IO.',
      priority: 'critical',
    },
    {
      title: 'Ground of belief recorded under S.42',
      description:
        'Empowered officer records grounds in writing before search. Without this, the entire search is liable to be struck down.',
      priority: 'critical',
    },
  ],
  panchnama: [
    {
      title: 'S.50 NDPS option-form panchnama',
      description:
        'Pre-search written notice + suspect signature + pancha signature + IO signature. Without this, recovery collapses.',
      priority: 'critical',
    },
    {
      title: 'Sampling panchnama (40 g representative)',
      description:
        'Sample drawn from each package, sealed in pancha presence. CRCL Standing Order 1/89. Magistrate-attested sample for Court.',
      priority: 'critical',
    },
  ],
  evidence: [
    {
      title: 'Chain-of-custody log from seizure to FSL',
      description:
        'Each transfer logged with timestamp + officer name + seal-condition photograph. Receipt seal at FSL must match dispatch seal.',
      priority: 'critical',
    },
  ],
  forensics: [
    {
      title: 'FSL chemical analysis report',
      description:
        'Confirms substance identity (heroin, cocaine, MDMA, etc.) and purity. Receipt-of-sample seal at FSL must match dispatch seal.',
      priority: 'critical',
    },
  ],
  bayan: [
    {
      title: 'Independent pancha bayans recorded same day',
      description:
        'Bayans of the two panchas recorded contemporaneously. Defence routinely impeaches stale or station-recorded bayans.',
      priority: 'critical',
    },
  ],
  safeguards: COMMON_SAFEGUARDS,
  gaps: [
    {
      title: 'S.50 NDPS notice not in writing',
      description:
        'Vijaysinh Chandubha Jadeja v. Gujarat (2011) 1 SCC 609 — strict compliance with S.50 mandatory. Notice in writing, option to be searched before Gazetted Officer / Magistrate, suspect signature.',
      priority: 'critical',
    },
    {
      title: 'Sample seal broken en route to FSL',
      description:
        'Mohanlal v. Rajasthan (2015) 6 SCC 222 — sampling, sealing, dispatch must be unbroken chain. Any seal break en route is fatal.',
      priority: 'critical',
    },
  ],
};

const POCSO: CategoryContent = {
  bns: [
    {
      title: 'POCSO S.4 / S.6 — Penetrative / aggravated penetrative',
      description:
        'S.4: 10 y to life + fine. S.6 (aggravated): 20 y to life or death + fine. Special Court trial. Strict timelines under POCSO Rules.',
      priority: 'critical',
    },
    {
      title: 'POCSO S.19 — Mandatory reporting',
      description:
        'Any person aware must report. Failure to report — up to 6 m or fine. Police must record FIR even if reporter is not victim or guardian.',
      priority: 'critical',
    },
    {
      title: 'POCSO S.25 — Statement before Magistrate',
      description:
        'Statement of child recorded by Judicial Magistrate at child\'s residence or place of choice. Audio-video where feasible.',
      priority: 'critical',
    },
  ],
  immediate: [
    {
      title: 'Notification to CWC + Special Juvenile Police Unit',
      description:
        'Child Welfare Committee notified within 24 h. SJPU handles all interactions with child. No uniformed officer near child.',
      priority: 'critical',
    },
    {
      title: 'Medical examination at government hospital',
      description:
        'Within 24 h, woman doctor where available. Two-finger test prohibited. Comfort and counselling presence essential.',
      priority: 'critical',
    },
    {
      title: 'Statement at child\'s preferred location',
      description:
        'Child\'s home, CWC office, or any safe place — never police station. Recorded by woman officer with support person of child\'s choice present.',
      priority: 'critical',
    },
  ],
  panchnama: [
    {
      title: 'Spot panchnama at offence location',
      description:
        'Two panchas (one woman where possible), sketch, signs of struggle, items relevant to offence. Privacy considerations paramount.',
      priority: 'critical',
    },
  ],
  evidence: [
    {
      title: 'Medical examination report (MER)',
      description:
        'Findings, age estimation, mental capacity. Two-finger test prohibited; use objective markers.',
      priority: 'critical',
    },
  ],
  forensics: [
    {
      title: 'DNA + biological sample analysis',
      description:
        'Vaginal swabs, clothing, scene articles. Cold-chain mandatory; FSL within 72 h.',
      priority: 'critical',
    },
  ],
  bayan: [
    {
      title: 'Child statement under POCSO S.25',
      description:
        'Recorded by Judicial Magistrate at child\'s preferred location. Audio-video where feasible. Substantive evidence.',
      priority: 'critical',
    },
    {
      title: 'First-disclosed-to person',
      description:
        'Teacher / parent / counsellor to whom child first disclosed. Admissible as res gestae if soon after.',
      priority: 'critical',
    },
  ],
  safeguards: [
    {
      title: 'Identity protection — POCSO S.23',
      description:
        'Child identity not disclosed in any record / order / judgment. Print + electronic media restraint. Anonymisation in chargesheet.',
      priority: 'critical',
    },
    {
      title: 'Trial timeline — within 1 year',
      description:
        'POCSO S.35 — evidence within 30 days of cognizance, trial completed within 1 year. Special Public Prosecutor under S.32.',
      priority: 'recommended',
    },
  ],
  gaps: [
    {
      title: 'Age proof not on record (school + bone-age)',
      description:
        'Birth certificate / school admission record primary. Ossification test secondary. Borderline age — benefit goes to prosecution under POCSO presumption.',
      priority: 'critical',
    },
    {
      title: 'Child witness competence not voire-dire-d',
      description:
        'Child\'s testimony admissible if able to understand questions and give rational answers (BSA S.124). Voire dire by court to establish competence.',
      priority: 'recommended',
    },
  ],
};

const GENERIC: CategoryContent = {
  bns: [
    {
      title: 'BNSS S.173 — FIR registration',
      description:
        'Mandatory for any cognizable offence. Verbatim record, free copy to informant, electronic registration permitted, Zero FIR if outside jurisdiction.',
      priority: 'critical',
    },
    {
      title: 'BNSS S.180 — Examination of witnesses by police',
      description:
        'Witness statement during investigation. Not admissible as substantive evidence but usable for contradiction under BSA S.145.',
      priority: 'critical',
    },
    COMMON_BSA63,
  ],
  immediate: [
    {
      title: 'Secure scene + photograph before disturbance',
      description:
        'Cordon off, scene entry log, photograph wide → mid → close. Tarpaulin overhead if outdoor and weather threatens.',
      priority: 'critical',
    },
    {
      title: 'Identify and approach witnesses',
      description:
        'Walk-around to identify potential witnesses. Note positions, contact details, retention plan. Record S.180 BNSS bayans same day.',
      priority: 'critical',
    },
  ],
  panchnama: [
    {
      title: 'Spot panchnama with two independent panchas',
      description:
        'Locality residents, unrelated to parties, mobile recorded. Single most-cited reason for HC seizure-doubt orders.',
      priority: 'critical',
    },
  ],
  evidence: [
    {
      title: 'Seize physical exhibits with chain of custody',
      description:
        'Each item separately packaged, exhibit-numbered, sealed in pancha presence. Hash any electronic media at seizure.',
      priority: 'critical',
    },
  ],
  bayan: [
    {
      title: 'Eyewitness bayan — same day, vernacular',
      description:
        'Verbatim, in witness\'s own language, read back, signed. Position, lighting, sequence of events.',
      priority: 'critical',
    },
  ],
  safeguards: COMMON_SAFEGUARDS,
  gaps: [
    {
      title: 'FIR registration delay without recorded explanation',
      description:
        'Sharad Birdhichand Sarda (1984) 4 SCC 116 — unexplained delay is a fatal infirmity. Record contemporaneous explanation in case diary.',
      priority: 'recommended',
    },
  ],
};

// ─── Tree builder ──────────────────────────────────────────────────────────

const CONTENT_REGISTRY: Record<string, CategoryContent> = {
  murder: MURDER,
  theft: THEFT,
  rape: RAPE,
  cyber_crime: CYBER,
  accident: ACCIDENT,
  dowry: DOWRY,
  missing_persons: MISSING,
  ndps: NDPS,
  pocso: POCSO,
  generic: GENERIC,
};

const CATEGORY_DISPLAY: Record<string, string> = {
  murder: 'Murder (BNS S.103)',
  theft: 'Theft (BNS S.303)',
  rape: 'Rape (BNS S.64)',
  cyber_crime: 'Cyber Crime (IT Act + BNS)',
  accident: 'Accident / Death by negligence',
  dowry: 'Dowry death (BNS S.80)',
  missing_persons: 'Missing Persons',
  ndps: 'NDPS',
  pocso: 'POCSO',
  generic: 'Generic',
};

interface DemoOptions {
  /** Use the actual FIR registration number in the centre hub label.
   *  Falls back to a placeholder when omitted. */
  firNumber?: string | null;
}

/**
 * Build a center-hub mindmap for the given category.
 *
 * Center: "FIR {number} | {category-display}"
 * Primary branches (in fixed order): the 7 substantive slots (BNS,
 * Immediate, Panchnama, Evidence, Forensics, Bayan, Safeguards) plus
 * Common FIR Gaps when the category has any.
 */
function buildDemo(category: string, opts: DemoOptions = {}): MindmapData {
  const content = CONTENT_REGISTRY[category] ?? GENERIC;
  const displayName = CATEGORY_DISPLAY[category] ?? category;
  const firLabel = opts.firNumber ? `FIR ${opts.firNumber}` : 'New FIR';

  let order = 0;
  const mindmapId = `demo-${category}`;
  const rootId = `${mindmapId}-root`;

  const nodes: MindmapNode[] = [];

  const root: MindmapNode = {
    id: rootId,
    mindmap_id: mindmapId,
    parent_id: null,
    node_type: 'evidence',
    title: `${firLabel}  |  ${displayName}`,
    description_md:
      'Demo mindmap rendered from a per-category template. Will be ' +
      'replaced by KB-driven content once the live 3-layer KB is connected.',
    source: 'static_template',
    bns_section: null,
    ipc_section: null,
    crpc_section: null,
    priority: 'critical',
    requires_disclaimer: false,
    display_order: order++,
    metadata: { demo: true, hub: true },
    current_status: null,
    children: [],
  };
  nodes.push(root);

  for (const slot of SLOT_ORDER) {
    const meta = SLOTS[slot];
    const leaves = content[slot];
    if (!leaves || leaves.length === 0) {
      // Skip slots with no content (most relevant for `gaps`, which is
      // only shown when actual gaps are detected).
      continue;
    }

    const branchId = `${mindmapId}-${slot}`;
    const emoji = SLOT_EMOJI[slot];
    const branchNode: MindmapNode = {
      id: branchId,
      mindmap_id: mindmapId,
      parent_id: rootId,
      node_type: meta.node_type,
      title: `${emoji}  ${meta.title}`,
      description_md: `${leaves.length} ${leaves.length === 1 ? 'item' : 'items'}`,
      source: 'static_template',
      bns_section: null,
      ipc_section: null,
      crpc_section: null,
      priority: 'critical',
      requires_disclaimer: slot === 'gaps',
      display_order: order++,
      metadata: {
        demo: true,
        slot,
        emoji,
        kb_layer: meta.layer,
        branch_type: meta.node_type,
      },
      current_status: null,
      children: [],
    };
    nodes.push(branchNode);
    root.children.push(branchNode);

    leaves.forEach((leaf, i) => {
      const leafNode: MindmapNode = {
        id: `${branchId}-${i}`,
        mindmap_id: mindmapId,
        parent_id: branchId,
        node_type: meta.node_type,
        title: leaf.title,
        description_md: leaf.description,
        source: 'static_template',
        bns_section: leaf.bns_section ?? null,
        ipc_section: leaf.ipc_section ?? null,
        crpc_section: leaf.crpc_section ?? null,
        priority: leaf.priority ?? 'recommended',
        requires_disclaimer: meta.layer === 'case_law_intelligence',
        display_order: order++,
        metadata: {
          demo: true,
          slot,
          kb_layer: meta.layer,
          branch_type: meta.node_type,
        },
        current_status: null,
        children: [],
      };
      nodes.push(leafNode);
      branchNode.children.push(leafNode);
    });
  }

  return {
    id: mindmapId,
    fir_id: `demo-fir-${category}`,
    case_category: category,
    template_version: 'demo-2.0.0-radial',
    generated_at: new Date().toISOString(),
    generated_by_model_version: 'demo-mindmap-radial-v1',
    root_node_id: rootId,
    status: 'active',
    nodes: [root],
    disclaimer:
      'Demo mindmap — static per-category template shown until the live ' +
      '3-layer KB is connected. The IO must not rely on this for case-' +
      'specific guidance.',
  };
}

/**
 * Return a static demo mindmap for the given case category. Falls back
 * to `generic` when the category is unknown or omitted.
 */
export function getDemoMindmap(
  caseCategory: string | undefined | null,
  opts: DemoOptions = {}
): MindmapData {
  const key = caseCategory && CONTENT_REGISTRY[caseCategory] ? caseCategory : 'generic';
  return buildDemo(key, opts);
}

/** Categories with demo coverage — for diagnostics / debug UI. */
export const DEMO_CATEGORIES = Object.keys(CONTENT_REGISTRY);
