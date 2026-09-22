export const BUILD = '91493d637f81';
/* Facts about the Layer 1 pipeline that the pages state but the bundle does
 * not carry. Layer 1 is closed, so these never move. They are defined once
 * here so that no two sentences on the site can disagree about them.
 */

/* The years the model was fitted on, as the pages print them.
   src/03_split.py: train is issue years 2014-2016. */
export const TRAIN_YEARS = '2014–2016';

/* The held-out year. src/03_split.py: train is issue years 2014-2016, test
   is issue year 2017. */
export const TEST_YEAR = 2017;
