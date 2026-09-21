using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using SolidWorks.Interop.sldworks;

public static class B51R1S05R2DriverReadyCarrierTool
{
    private const int PartType = 1;
    private const int OpenSilent = 1;
    private const int OpenReadOnly = 2;
    private const int CoincidentConstraint = 4;
    private const double Length = 0.02;
    private const double DirectionTolerance = 1.0e-9;
    private const double PositionTolerance = 1.0e-8;
    private const string UrdfSha = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164";

    private static readonly string[,] Properties =
    {
        {"MODEL_ROLE", "KINEMATIC_CARRIER"},
        {"DYNAMIC_AUTHORITY", "ACCEPTED_URDF"},
        {"CAD_MASS_CONTRIBUTION", "ZERO"},
        {"BOM_EXCLUDE", "TRUE"},
        {"SOURCE_URDF_SHA256", UrdfSha}
    };

    private sealed class Spec
    {
        internal string Link;
        internal string Joint;
        internal double Lower;
        internal double AxisSign;
        internal int CoordinateSystemCount;
        internal int ExpectedFeatureCount;
        internal bool Root;
        internal string IncomingJoint;
        internal double[] IncomingAxis;
        internal bool FixedIncoming;
        internal string FixedOutgoingJoint;
        internal string[] PrismaticOutgoingJoints;
        internal bool HasLimitReference { get { return Joint != null; } }
        internal string InputFile { get { return "B51R1_CARRIER_MR1_" + Link + ".SLDPRT"; } }
        internal string OutputFile { get { return "B51R1_CARRIER_MR2_" + Link + ".SLDPRT"; } }
    }

    private sealed class FrameData
    {
        internal double[] Origin;
        internal double[] Ex;
        internal double[] Ey;
        internal double[] Ez;
        internal double[] Axis;
        internal double[] LimitTangent;
        internal double[] LimitNormal;
    }

    private sealed class ExpectedFrame
    {
        internal string Joint;
        internal double X, Y, Z, Rx, Ry, Rz;
        internal ExpectedFrame(string joint,double x,double y,double z,double rx,double ry,double rz)
        {
            Joint=joint; X=x; Y=y; Z=z; Rx=rx; Ry=ry; Rz=rz;
        }
    }

    private sealed class FileLock
    {
        internal string Link;
        internal string Path;
        internal long Bytes;
        internal string Sha256;
    }

    private sealed class StagedPublication
    {
        internal string StagedInput;
        internal string StagedOutput;
        internal string FinalOutput;
        internal Dictionary<string,object> Evidence;
    }

    private static List<Spec> Specs()
    {
        return new List<Spec>
        {
            new Spec{Link="base_link",Joint="joint1",Lower=-2.8,AxisSign=1,CoordinateSystemCount=3,
                ExpectedFeatureCount=27,Root=true},
            new Spec{Link="link1",Joint="joint2",Lower=-3.14,AxisSign=-1,CoordinateSystemCount=4,
                ExpectedFeatureCount=29,IncomingJoint="joint1",IncomingAxis=new[]{0.0,0.0,1.0}},
            new Spec{Link="link2",Joint="joint3",Lower=-3.14,AxisSign=1,CoordinateSystemCount=4,
                ExpectedFeatureCount=29,IncomingJoint="joint2",IncomingAxis=new[]{0.0,0.0,-1.0}},
            new Spec{Link="link3",Joint="joint4",Lower=-1.87,AxisSign=1,CoordinateSystemCount=4,
                ExpectedFeatureCount=29,IncomingJoint="joint3",IncomingAxis=new[]{0.0,0.0,1.0}},
            new Spec{Link="link4",Joint="joint5",Lower=-1.57,AxisSign=1,CoordinateSystemCount=4,
                ExpectedFeatureCount=29,IncomingJoint="joint4",IncomingAxis=new[]{0.0,0.0,1.0}},
            new Spec{Link="link5",Joint="joint6",Lower=-3.14,AxisSign=1,CoordinateSystemCount=4,
                ExpectedFeatureCount=29,IncomingJoint="joint5",IncomingAxis=new[]{0.0,0.0,1.0}},
            new Spec{Link="link6",CoordinateSystemCount=4,ExpectedFeatureCount=27,
                IncomingJoint="joint6",IncomingAxis=new[]{0.0,0.0,1.0},FixedOutgoingJoint="gripper_joint"},
            new Spec{Link="gripper_link",CoordinateSystemCount=5,ExpectedFeatureCount=31,
                IncomingJoint="gripper_joint",FixedIncoming=true,
                PrismaticOutgoingJoints=new[]{"gripper_joint1","gripper_joint2"}},
            new Spec{Link="gripper_left",CoordinateSystemCount=3,ExpectedFeatureCount=22,
                IncomingJoint="gripper_joint1",IncomingAxis=new[]{1.0,0.0,0.0}},
            new Spec{Link="gripper_right",CoordinateSystemCount=3,ExpectedFeatureCount=22,
                IncomingJoint="gripper_joint2",IncomingAxis=new[]{1.0,0.0,0.0}}
        };
    }

    private static ExpectedFrame ExpectedParentFrame(string joint)
    {
        if(joint=="joint1") return new ExpectedFrame(joint,-8.416e-5,0,0.08465,0,0,0);
        if(joint=="joint2") return new ExpectedFrame(joint,0.020084,0.031625,0.05555,-1.5708,0,0);
        if(joint=="joint3") return new ExpectedFrame(joint,-0.264,0,0,0,0,0);
        if(joint=="joint4") return new ExpectedFrame(joint,0.2426,-0.054,-0.001625,0,0,0);
        if(joint=="joint5") return new ExpectedFrame(joint,0.078308,-0.0375,-0.03,-1.5708,0,0);
        if(joint=="joint6") return new ExpectedFrame(joint,0.023692,0,0.04,0,1.5708,0);
        if(joint=="gripper_joint") return new ExpectedFrame(joint,0,0,0.15971,0,-1.5708,0);
        if(joint=="gripper_joint1") return new ExpectedFrame(joint,-0.042091,2.7531e-5,-1.3031e-5,0,0,-1.5708);
        if(joint=="gripper_joint2") return new ExpectedFrame(joint,-0.042091,-2.7531e-5,1.3031e-5,0,0,1.5708);
        throw new InvalidOperationException("No accepted parent frame for " + joint);
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static void ReleaseCom(object value)
    {
        if (value == null || !Marshal.IsComObject(value)) return;
        try { Marshal.FinalReleaseComObject(value); } catch { }
    }

    private static string Sha256(string path)
    {
        using (FileStream stream = File.OpenRead(path))
        using (SHA256 digest = SHA256.Create())
            return BitConverter.ToString(digest.ComputeHash(stream)).Replace("-", "");
    }

    private static void WriteJsonCreateNew(string path, Dictionary<string, object> data)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        using (FileStream stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
        using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
            writer.Write(new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue }.Serialize(data));
    }

    private static void ProgressCreateNew(string path, string line)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        using (FileStream stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
        using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false))) writer.WriteLine(line);
    }

    private static void Progress(string path, string line)
    {
        using (FileStream stream = new FileStream(path, FileMode.Append, FileAccess.Write, FileShare.Read))
        using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false))) writer.WriteLine(line);
    }

    private static SldWorks Attach(int expectedProcessId)
    {
        SldWorks app = (SldWorks)Marshal.GetActiveObject("SldWorks.Application");
        Require(app.GetProcessID() == expectedProcessId, "ROT PID mismatch");
        Require(app.Visible && app.StartupProcessCompleted, "SOLIDWORKS is not ready");
        Require(app.GetDocumentCount() == 0 && app.ActiveDoc == null, "Session is not empty");
        return app;
    }

    private static Feature[] TopLevelFeatures(ModelDoc2 model)
    {
        FeatureManager manager=null;
        try
        {
            manager=model.FeatureManager; Array values=manager.GetFeatures(true) as Array;
            if(values==null) return new Feature[0];
            var result=new List<Feature>();
            foreach(object value in values)
            {
                Feature feature=value as Feature;
                if(feature!=null) result.Add(feature);
            }
            return result.ToArray();
        }
        finally { ReleaseCom(manager); }
    }

    private static int FeatureCount(ModelDoc2 model)
    {
        Feature[] features = TopLevelFeatures(model);
        try { return features.Length; }
        finally { foreach (Feature feature in features) ReleaseCom(feature); }
    }

    private static int FeatureTypeCount(ModelDoc2 model, string type)
    {
        int count = 0; Feature[] features = TopLevelFeatures(model);
        try { foreach (Feature feature in features) if (feature.GetTypeName2() == type) count++; return count; }
        finally { foreach (Feature feature in features) ReleaseCom(feature); }
    }

    private static HashSet<string> FeatureKeys(ModelDoc2 model)
    {
        var result = new HashSet<string>(StringComparer.Ordinal);
        Feature[] features = TopLevelFeatures(model);
        try
        {
            foreach (Feature feature in features) result.Add(feature.GetTypeName2()+"|"+feature.Name);
            return result;
        }
        finally { foreach (Feature feature in features) ReleaseCom(feature); }
    }

    private static Feature FindNewFeature(ModelDoc2 model, HashSet<string> before, string type)
    {
        Feature[] features = TopLevelFeatures(model); Feature match = null; int count = 0;
        try
        {
            foreach (Feature feature in features)
            {
                string key = feature.GetTypeName2()+"|"+feature.Name;
                if (!before.Contains(key) && feature.GetTypeName2() == type)
                {
                    count++; if (match == null) match = feature; else ReleaseCom(feature);
                }
                else ReleaseCom(feature);
            }
            Require(count==1 && match!=null,"Expected one new "+type+" feature; count="+count);
            return match;
        }
        catch { ReleaseCom(match); throw; }
    }

    private static Feature FindUniqueFeature(ModelDoc2 model, string name, string type)
    {
        Feature[] features=TopLevelFeatures(model); Feature match=null; int count=0;
        try
        {
            foreach(Feature feature in features)
            {
                if(feature.Name==name && feature.GetTypeName2()==type)
                {
                    count++; if(match==null) match=feature; else ReleaseCom(feature);
                }
                else ReleaseCom(feature);
            }
            Require(count==1&&match!=null,"Expected one "+type+" feature: "+name+"; count="+count);
            return match;
        }
        catch { ReleaseCom(match); throw; }
    }

    private static int FeatureNameCount(ModelDoc2 model,string name)
    {
        int count=0; Feature[] features=TopLevelFeatures(model);
        try { foreach(Feature feature in features) if(feature.Name==name) count++; return count; }
        finally { foreach(Feature feature in features) ReleaseCom(feature); }
    }

    private static void RequireFeatureAbsent(ModelDoc2 model,string name)
    {
        Require(FeatureNameCount(model,name)==0,"Target feature already exists: "+name);
    }

    private static double[] ToArray(object raw, int length)
    {
        Array values=raw as Array; Require(values!=null&&values.Length==length,"Array length mismatch");
        double[] result=new double[length]; int i=0; foreach(object value in values) result[i++]=Convert.ToDouble(value);
        return result;
    }

    private static double Dot(double[] a,double[] b)
    {
        return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
    }

    private static double Norm(double[] a)
    {
        return Math.Sqrt(Dot(a,a));
    }

    private static double[] Scale(double[] a,double value)
    {
        return new[]{a[0]*value,a[1]*value,a[2]*value};
    }

    private static double[] Add(double[] a,double[] b)
    {
        return new[]{a[0]+b[0],a[1]+b[1],a[2]+b[2]};
    }

    private static double[] Cross(double[] a,double[] b)
    {
        return new[]{a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};
    }

    private static double[] Normalize(double[] value)
    {
        double n=Norm(value); Require(n>0,"Zero vector"); return Scale(value,1.0/n);
    }

    private static double[] Rotate(double[] value,double[] rawAxis,double angle)
    {
        double[] axis=Normalize(rawAxis); double c=Math.Cos(angle),s=Math.Sin(angle);
        return Add(Add(Scale(value,c),Scale(Cross(axis,value),s)),Scale(axis,Dot(axis,value)*(1-c)));
    }

    private static double[] Unit(int index)
    {
        double[] value={0,0,0}; value[index]=1; return value;
    }

    private static int AxisIndex(double[] axis)
    {
        for(int i=0;i<3;i++) if(Math.Abs(axis[i])>0.5) return i;
        throw new InvalidOperationException("Joint axis is not canonical");
    }

    private static double[] Apply(FrameData frame,double[] local)
    {
        return Add(Add(Scale(frame.Ex,local[0]),Scale(frame.Ey,local[1])),Scale(frame.Ez,local[2]));
    }

    private static double[] Apply(ExpectedFrame frame,double[] local)
    {
        double sx=Math.Sin(frame.Rx),cx=Math.Cos(frame.Rx);
        double sy=Math.Sin(frame.Ry),cy=Math.Cos(frame.Ry);
        double sz=Math.Sin(frame.Rz),cz=Math.Cos(frame.Rz);
        return new[]
        {
            cy*cz*local[0]+(sx*sy*cz-cx*sz)*local[1]+(cx*sy*cz+sx*sz)*local[2],
            cy*sz*local[0]+(sx*sy*sz+cx*cz)*local[1]+(cx*sy*sz-sx*cz)*local[2],
            -sy*local[0]+sx*cy*local[1]+cx*cy*local[2]
        };
    }

    private static double[] ExpectedTransform(ExpectedFrame frame)
    {
        double[] ex=Apply(frame,Unit(0)),ey=Apply(frame,Unit(1)),ez=Apply(frame,Unit(2));
        return new[]{ex[0],ex[1],ex[2],ey[0],ey[1],ey[2],ez[0],ez[1],ez[2],
            frame.X,frame.Y,frame.Z,1.0,0.0,0.0,0.0};
    }

    private static double[] IdentityTransform()
    {
        return new[]{1.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0};
    }

    private static FrameData ReadCoordinateFrame(ModelDoc2 model,string joint)
    {
        ModelDocExtension extension=null; MathTransform transform=null;
        try
        {
            extension=model.Extension;
            transform=extension.GetCoordinateSystemTransformByName("CS_JOINT_"+joint+"_PARENT_SIDE");
            Require(transform!=null,"Parent coordinate system missing: "+joint);
            double[] raw=ToArray(transform.ArrayData,16);
            return new FrameData
            {
                Ex=new[]{raw[0],raw[1],raw[2]},Ey=new[]{raw[3],raw[4],raw[5]},Ez=new[]{raw[6],raw[7],raw[8]},
                Origin=new[]{raw[9],raw[10],raw[11]}
            };
        }
        finally { ReleaseCom(transform); ReleaseCom(extension); }
    }

    private static FrameData ReadFrame(ModelDoc2 model, Spec spec)
    {
        FrameData frame=ReadCoordinateFrame(model,spec.Joint);
        frame.Axis=Scale(frame.Ez,spec.AxisSign);
        frame.LimitTangent=Rotate(frame.Ex,frame.Axis,spec.Lower);
        frame.LimitNormal=Normalize(Cross(frame.Axis,frame.LimitTangent));
        return frame;
    }

    private static Feature AddLimitReference(ModelDoc2 model, Spec spec)
    {
        FrameData frame=ReadFrame(model,spec);
        string sketchName="SK3D_LIMIT_"+spec.Joint+"_PARENT_SIDE";
        string planeName="PLANE_LIMIT_REF_"+spec.Joint+"_PARENT_SIDE";
        RequireFeatureAbsent(model,sketchName); RequireFeatureAbsent(model,planeName);
        int featureCountBefore=FeatureCount(model);
        SketchManager manager=model.SketchManager;
        bool oldAdd=manager.AddToDB,oldDisplay=manager.DisplayWhenAdded;
        SketchPoint[] points=null; Feature sketch=null; Feature planeFeature=null;
        try
        {
            HashSet<string> beforeSketch=FeatureKeys(model);
            manager.AddToDB=true; manager.DisplayWhenAdded=false; manager.Insert3DSketch(true);
            double[] p1=Add(frame.Origin,Scale(frame.Axis,Length));
            double[] p2=Add(frame.Origin,Scale(frame.LimitTangent,Length));
            points=new[]
            {
                manager.CreatePoint(frame.Origin[0],frame.Origin[1],frame.Origin[2]),
                manager.CreatePoint(p1[0],p1[1],p1[2]),
                manager.CreatePoint(p2[0],p2[1],p2[2])
            };
            Require(points[0]!=null&&points[1]!=null&&points[2]!=null,"Limit-reference sketch point creation failed");
            for(int i=0;i<points.Length;i++)
            {
                model.ClearSelection2(true);
                Require(points[i].Select2(false,0),"Limit point fixed-relation selection failed: "+i);
                model.SketchAddConstraints("sgFIXED");
            }
            model.ClearSelection2(true);
            manager.Insert3DSketch(true);
            sketch=FindNewFeature(model,beforeSketch,"3DProfileFeature");
            sketch.Name=sketchName; Require(sketch.Name==sketchName,"Limit sketch rename failed: "+spec.Joint);

            HashSet<string> beforePlane=FeatureKeys(model);
            model.ClearSelection2(true);
            Require(points[0].Select2(false,0),"Limit point 0 selection failed");
            Require(points[1].Select2(true,1),"Limit point 1 selection failed");
            Require(points[2].Select2(true,2),"Limit point 2 selection failed");
            FeatureManager featureManager=null; object created=null;
            try
            {
                featureManager=model.FeatureManager;
                created=featureManager.InsertRefPlane(
                    CoincidentConstraint,0,CoincidentConstraint,0,CoincidentConstraint,0);
                Require(created!=null,"Limit-reference InsertRefPlane failed");
            }
            finally { ReleaseCom(created); ReleaseCom(featureManager); }
            model.ClearSelection2(true);
            planeFeature=FindNewFeature(model,beforePlane,"RefPlane");
            planeFeature.Name=planeName; Require(planeFeature.Name==planeName,"Limit plane rename failed: "+spec.Joint);
            Require(FeatureCount(model)==featureCountBefore+2,"Limit-reference feature delta is not exactly +2: "+spec.Joint);
            Feature result=planeFeature; planeFeature=null; return result;
        }
        catch
        {
            try { if(manager.ActiveSketch!=null) manager.Insert3DSketch(true); } catch { }
            throw;
        }
        finally
        {
            manager.AddToDB=oldAdd; manager.DisplayWhenAdded=oldDisplay;
            if(points!=null) foreach(SketchPoint point in points) ReleaseCom(point);
            ReleaseCom(planeFeature); ReleaseCom(sketch); ReleaseCom(manager);
        }
    }

    private static int BodyCount(ModelDoc2 model)
    {
        Array bodies=((PartDoc)model).GetBodies2(-1,false) as Array;
        if(bodies==null) return 0;
        try { return bodies.Length; } finally { foreach(object body in bodies) ReleaseCom(body); }
    }

    private static Dictionary<string,object> MassEvidence(ModelDoc2 model)
    {
        ModelDocExtension extension=null;
        try
        {
            extension=model.Extension; int status; Array values=extension.GetMassProperties2(2,out status,false) as Array;
            Require(status==2,"Expected NoBody mass status; observed "+status);
            return new Dictionary<string,object>{{"status",status},{"returned_value_count",values==null?0:values.Length},{"cad_mass_kg",0.0}};
        }
        finally { ReleaseCom(extension); }
    }

    private static List<Dictionary<string,object>> ReadProperties(ModelDoc2 model)
    {
        ModelDocExtension extension=null; CustomPropertyManager manager=null;
        var result=new List<Dictionary<string,object>>();
        try
        {
            extension=model.Extension; manager=extension.get_CustomPropertyManager("");
            for(int i=0;i<Properties.GetLength(0);i++)
            {
                string raw,resolved; bool wasResolved,linked;
                int get=manager.Get6(Properties[i,0],false,out raw,out resolved,out wasResolved,out linked);
                int type=manager.GetType2(Properties[i,0]);
                Require(get!=0&&type==30&&raw==Properties[i,1]&&resolved==Properties[i,1],"Property mismatch: "+Properties[i,0]);
                result.Add(new Dictionary<string,object>{{"name",Properties[i,0]},{"value",resolved},{"type",type}});
            }
            return result;
        }
        finally { ReleaseCom(manager); ReleaseCom(extension); }
    }

    private static Dictionary<string,object> InspectCoordinateSystem(ModelDoc2 model,string name,double[] expected)
    {
        ModelDocExtension extension=null; MathTransform transform=null;
        try
        {
            extension=model.Extension; transform=extension.GetCoordinateSystemTransformByName(name);
            Require(transform!=null,"Coordinate system missing: "+name);
            double[] raw=ToArray(transform.ArrayData,16); double error=0;
            for(int i=0;i<16;i++) error=Math.Max(error,Math.Abs(raw[i]-expected[i]));
            Require(error<=1.0e-12,"Coordinate-system transform mismatch: "+name+"; error="+error);
            return new Dictionary<string,object>{{"name",name},{"raw_transform",raw},{"maximum_absolute_error",error}};
        }
        finally { ReleaseCom(transform); ReleaseCom(extension); }
    }

    private static Dictionary<string,object> InspectAxis(ModelDoc2 model,string name,double[] point,double[] direction)
    {
        Feature feature=null; RefAxis axis=null;
        try
        {
            feature=FindUniqueFeature(model,name,"RefAxis"); axis=feature.GetSpecificFeature2() as RefAxis;
            Require(axis!=null,"IRefAxis unavailable: "+name); double[] p=ToArray(axis.GetRefAxisParams(),6);
            double[] d={p[3]-p[0],p[4]-p[1],p[5]-p[2]};
            double alignment=Math.Abs(Dot(d,direction)/(Norm(d)*Norm(direction)));
            double[] r={point[0]-p[0],point[1]-p[1],point[2]-p[2]}; double error=Norm(Cross(r,d))/Norm(d);
            Require(alignment>=1-DirectionTolerance&&error<=PositionTolerance,
                name+" geometry mismatch; alignment="+alignment+", error="+error);
            return new Dictionary<string,object>{{"name",name},{"endpoints",p},{"absolute_alignment",alignment},{"point_to_line_error_m",error}};
        }
        finally { ReleaseCom(axis); ReleaseCom(feature); }
    }

    private static Dictionary<string,object> InspectLimitSketch(ModelDoc2 model,Spec spec,FrameData frame)
    {
        Feature feature=null; Sketch sketch=null; Array rawPoints=null; Array rawSegments=null;
        try
        {
            string name="SK3D_LIMIT_"+spec.Joint+"_PARENT_SIDE";
            feature=FindUniqueFeature(model,name,"3DProfileFeature"); sketch=feature.GetSpecificFeature2() as Sketch;
            Require(sketch!=null,"ISketch unavailable: "+name); rawPoints=sketch.GetSketchPoints2() as Array;
            rawSegments=sketch.GetSketchSegments() as Array;
            Require(rawPoints!=null&&rawPoints.Length==3,"Limit sketch must contain exactly three points: "+name);
            Require(rawSegments==null||rawSegments.Length==0,"Limit sketch must not contain segments: "+name);
            double[][] expected={frame.Origin,Add(frame.Origin,Scale(frame.Axis,Length)),Add(frame.Origin,Scale(frame.LimitTangent,Length))};
            var observed=new List<double[]>();
            foreach(object value in rawPoints)
            {
                SketchPoint point=value as SketchPoint; Require(point!=null,"Limit sketch point RCW unavailable: "+name);
                observed.Add(new[]{point.X,point.Y,point.Z});
            }
            double maxError=0;
            foreach(double[] target in expected)
            {
                double best=Double.MaxValue;
                foreach(double[] value in observed)
                {
                    double dx=target[0]-value[0],dy=target[1]-value[1],dz=target[2]-value[2];
                    best=Math.Min(best,Math.Sqrt(dx*dx+dy*dy+dz*dz));
                }
                maxError=Math.Max(maxError,best);
            }
            Require(maxError<=PositionTolerance,"Limit sketch point geometry mismatch: "+name+"; error="+maxError);
            return new Dictionary<string,object>{{"name",name},{"point_count",3},{"segment_count",0},{"maximum_point_error_m",maxError}};
        }
        finally
        {
            if(rawPoints!=null) foreach(object value in rawPoints) ReleaseCom(value);
            if(rawSegments!=null) foreach(object value in rawSegments) ReleaseCom(value);
            ReleaseCom(sketch); ReleaseCom(feature);
        }
    }

    private static Dictionary<string,object> InspectPlane(ModelDoc2 model,string name,double[] point,double[] normal)
    {
        Feature feature=null; RefPlane plane=null; MathTransform transform=null;
        try
        {
            feature=FindUniqueFeature(model,name,"RefPlane"); plane=feature.GetSpecificFeature2() as RefPlane;
            Require(plane!=null,"IRefPlane unavailable: "+name); transform=plane.Transform;
            double[] raw=ToArray(transform.ArrayData,16); double[] observed={raw[6],raw[7],raw[8]};
            double alignment=Math.Abs(Dot(observed,normal)/(Norm(observed)*Norm(normal)));
            double[] delta={point[0]-raw[9],point[1]-raw[10],point[2]-raw[11]};
            double error=Math.Abs(Dot(observed,delta))/Norm(observed);
            Require(alignment>=1-DirectionTolerance&&error<=PositionTolerance,
                name+" geometry mismatch; alignment="+alignment+", error="+error);
            return new Dictionary<string,object>{{"name",name},{"absolute_alignment",alignment},{"point_to_plane_error_m",error},{"raw_transform",raw}};
        }
        finally { ReleaseCom(transform); ReleaseCom(plane); ReleaseCom(feature); }
    }

    private static Dictionary<string,object> Inspect(ModelDoc2 model,Spec spec)
    {
        Require(BodyCount(model)==0,spec.Link+" has bodies");
        Require(model.ListExternalFileReferencesCount2()==0,spec.Link+" has external references");
        Require(FeatureTypeCount(model,"CoordSys")==spec.CoordinateSystemCount,spec.Link+" coordinate-system count changed");
        Require(FeatureCount(model)==spec.ExpectedFeatureCount,
            spec.Link+" feature inventory changed; expected="+spec.ExpectedFeatureCount+", observed="+FeatureCount(model));
        var coordinateSystems=new List<Dictionary<string,object>>();
        var inheritedRefs=new List<Dictionary<string,object>>();
        var driverRefs=new List<Dictionary<string,object>>();
        double[] identity=IdentityTransform(),origin={0,0,0};
        coordinateSystems.Add(InspectCoordinateSystem(model,"CS_LINK_"+spec.Link,identity));
        coordinateSystems.Add(InspectCoordinateSystem(model,"CS_VISUAL_MOUNT_"+spec.Link,identity));
        if(spec.IncomingJoint!=null)
            coordinateSystems.Add(InspectCoordinateSystem(model,"CS_JOINT_"+spec.IncomingJoint+"_CHILD_SIDE",identity));
        var outgoing=new List<string>();
        if(spec.Joint!=null) outgoing.Add(spec.Joint);
        if(spec.FixedOutgoingJoint!=null) outgoing.Add(spec.FixedOutgoingJoint);
        if(spec.PrismaticOutgoingJoints!=null) outgoing.AddRange(spec.PrismaticOutgoingJoints);
        foreach(string joint in outgoing)
            coordinateSystems.Add(InspectCoordinateSystem(model,"CS_JOINT_"+joint+"_PARENT_SIDE",
                ExpectedTransform(ExpectedParentFrame(joint))));

        if(spec.Root)
        {
            inheritedRefs.Add(InspectPlane(model,"ROOT_PLN_X",origin,Unit(0)));
            inheritedRefs.Add(InspectPlane(model,"ROOT_PLN_Y",origin,Unit(1)));
            inheritedRefs.Add(InspectPlane(model,"ROOT_PLN_Z",origin,Unit(2)));
        }
        if(spec.IncomingJoint!=null)
        {
            if(spec.FixedIncoming)
            {
                inheritedRefs.Add(InspectPlane(model,"GFIX_PLN_X",origin,Unit(0)));
                inheritedRefs.Add(InspectPlane(model,"GFIX_PLN_Y",origin,Unit(1)));
                inheritedRefs.Add(InspectPlane(model,"GFIX_PLN_Z",origin,Unit(2)));
            }
            else
            {
                int axisIndex=AxisIndex(spec.IncomingAxis);
                int zeroNormal=axisIndex==0?2:(axisIndex==1?0:1);
                inheritedRefs.Add(InspectAxis(model,"AXIS_"+spec.IncomingJoint,origin,spec.IncomingAxis));
                inheritedRefs.Add(InspectPlane(model,"PLANE_SEAT_"+spec.IncomingJoint+"_CHILD_SIDE",origin,Unit(axisIndex)));
                inheritedRefs.Add(InspectPlane(model,"PLANE_ZERO_"+spec.IncomingJoint,origin,Unit(zeroNormal)));
            }
        }
        if(spec.FixedOutgoingJoint!=null)
        {
            FrameData frame=ReadCoordinateFrame(model,spec.FixedOutgoingJoint);
            Feature sketch=FindUniqueFeature(model,"SK3D_DATUM_"+spec.FixedOutgoingJoint+"_PARENT_SIDE","3DProfileFeature");
            ReleaseCom(sketch);
            inheritedRefs.Add(InspectPlane(model,"GFIX_PLN_X_PARENT_SIDE",frame.Origin,frame.Ex));
            inheritedRefs.Add(InspectPlane(model,"GFIX_PLN_Y_PARENT_SIDE",frame.Origin,frame.Ey));
            inheritedRefs.Add(InspectPlane(model,"GFIX_PLN_Z_PARENT_SIDE",frame.Origin,frame.Ez));
        }
        if(spec.PrismaticOutgoingJoints!=null)
        {
            foreach(string joint in spec.PrismaticOutgoingJoints)
            {
                FrameData frame=ReadCoordinateFrame(model,joint);
                Feature sketch=FindUniqueFeature(model,"SK3D_DATUM_"+joint+"_PARENT_SIDE","3DProfileFeature");
                ReleaseCom(sketch);
                inheritedRefs.Add(InspectAxis(model,"AXIS_"+joint+"_PARENT_SIDE",frame.Origin,frame.Ex));
                inheritedRefs.Add(InspectPlane(model,"PLANE_SEAT_"+joint+"_PARENT_SIDE",frame.Origin,frame.Ex));
                inheritedRefs.Add(InspectPlane(model,"PLANE_ZERO_"+joint+"_PARENT_SIDE",frame.Origin,frame.Ez));
            }
        }
        if(spec.HasLimitReference)
        {
            FrameData frame=ReadFrame(model,spec);
            Feature inheritedSketch=FindUniqueFeature(model,"SK3D_DATUM_"+spec.Joint+"_PARENT_SIDE","3DProfileFeature");
            ReleaseCom(inheritedSketch);
            inheritedRefs.Add(InspectAxis(model,"AXIS_"+spec.Joint+"_PARENT_SIDE",frame.Origin,frame.Axis));
            inheritedRefs.Add(InspectPlane(model,"PLANE_SEAT_"+spec.Joint+"_PARENT_SIDE",frame.Origin,frame.Axis));
            inheritedRefs.Add(InspectPlane(model,"PLANE_ZERO_"+spec.Joint+"_PARENT_SIDE",frame.Origin,
                Normalize(Cross(frame.Axis,frame.Ex))));
            driverRefs.Add(InspectLimitSketch(model,spec,frame));
            driverRefs.Add(InspectPlane(model,"PLANE_LIMIT_REF_"+spec.Joint+"_PARENT_SIDE",frame.Origin,frame.LimitNormal));
        }
        return new Dictionary<string,object>
        {
            {"link",spec.Link},{"feature_count",FeatureCount(model)},{"coordinate_system_count",spec.CoordinateSystemCount},
            {"body_count",0},{"external_reference_count",0},{"mass_properties",MassEvidence(model)},
            {"properties",ReadProperties(model)},{"coordinate_systems",coordinateSystems},
            {"inherited_mate_reference_features",inheritedRefs},{"driver_reference_features",driverRefs}
        };
    }

    private static string Canonical(string path)
    {
        return Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar,Path.AltDirectorySeparatorChar);
    }

    private static bool SamePath(string a,string b)
    {
        return String.Equals(Canonical(a),Canonical(b),StringComparison.OrdinalIgnoreCase);
    }

    private static string ControlledRoot()
    {
        string assembly=typeof(B51R1S05R2DriverReadyCarrierTool).Assembly.Location;
        DirectoryInfo reviews=Directory.GetParent(Canonical(assembly));
        Require(reviews!=null&&reviews.Name=="08_REVIEWS"&&reviews.Parent!=null,
            "Tool assembly is not loaded from the controlled review directory");
        return reviews.Parent.FullName;
    }

    private static bool IsUnderDirectory(string path,string directory)
    {
        string candidate=Canonical(path),parent=Canonical(directory)+Path.DirectorySeparatorChar;
        return candidate.StartsWith(parent,StringComparison.OrdinalIgnoreCase);
    }

    private static string RequireControlledPaths(string inputDirectory,string outputDirectory,
        string receiptPath,string progressPath,string session)
    {
        string root=ControlledRoot();
        Require(SamePath(outputDirectory,Path.Combine(root,"03_CAD","12_DRIVER_READY_CARRIERS")),
            "Output directory is not the DLL-anchored controlled MR2 location");
        if(inputDirectory!=null)
            Require(SamePath(inputDirectory,Path.Combine(root,"03_CAD","11_MATE_READY_CARRIERS")),
                "Input directory is not the controlled MR1 location");
        string evidence=Path.Combine(root,"07_VERIFICATION","AUTONOMOUS",session);
        Require(SamePath(Path.GetDirectoryName(receiptPath),evidence)&&SamePath(Path.GetDirectoryName(progressPath),evidence),
            "Evidence paths are outside the controlled session directory");
        return root;
    }

    private static Dictionary<string,object> ReadJsonObject(string path)
    {
        Require(File.Exists(path),"Required JSON is missing: "+path);
        Dictionary<string,object> data=new JavaScriptSerializer { MaxJsonLength=Int32.MaxValue }
            .DeserializeObject(File.ReadAllText(path,Encoding.UTF8)) as Dictionary<string,object>;
        Require(data!=null,"Required JSON is not an object: "+path); return data;
    }

    private static void RequireReceiptBinding(string root,Dictionary<string,object> gate)
    {
        object raw; Require(gate.TryGetValue("receipt",out raw),"Gate receipt binding is missing");
        Dictionary<string,object> receipt=raw as Dictionary<string,object>;
        Require(receipt!=null&&receipt.ContainsKey("path")&&receipt.ContainsKey("bytes")&&receipt.ContainsKey("sha256"),
            "Gate receipt binding is incomplete");
        string path=Convert.ToString(receipt["path"]),expected=Convert.ToString(receipt["sha256"]);
        long bytes=Convert.ToInt64(receipt["bytes"]);
        Require(IsUnderDirectory(path,Path.Combine(root,"07_VERIFICATION","AUTONOMOUS")),
            "Gate receipt is outside controlled evidence: "+path);
        Require(File.Exists(path)&&new FileInfo(path).Length==bytes&&Sha256(path)==expected,
            "Gate receipt hash binding failed: "+path);
    }

    private static Dictionary<string,object> RequireJsonState(string root,string relativePath,
        string expectedStatus,bool expectedGatePass)
    {
        string path=Path.Combine(root,relativePath.Replace('/',Path.DirectorySeparatorChar));
        Dictionary<string,object> data=ReadJsonObject(path); object status,gatePass;
        Require(data.TryGetValue("status",out status)&&Convert.ToString(status)==expectedStatus,
            "Prerequisite status mismatch: "+relativePath);
        Require(data.TryGetValue("gate_pass",out gatePass)&&Convert.ToBoolean(gatePass)==expectedGatePass,
            "Prerequisite gate_pass mismatch: "+relativePath);
        if(expectedGatePass) RequireReceiptBinding(root,data); return data;
    }

    private static Dictionary<string,string> GatePartHashes(Dictionary<string,object> gate,string[] expectedLinks)
    {
        object raw; Require(gate.TryGetValue("parts",out raw),"Prerequisite Gate has no parts array");
        object[] parts=raw as object[]; Require(parts!=null&&parts.Length==expectedLinks.Length,
            "Prerequisite Gate part count mismatch");
        var result=new Dictionary<string,string>(StringComparer.Ordinal);
        foreach(object value in parts)
        {
            Dictionary<string,object> item=value as Dictionary<string,object>;
            Require(item!=null&&item.ContainsKey("link")&&item.ContainsKey("sha256"),"Prerequisite part evidence is incomplete");
            string link=Convert.ToString(item["link"]),sha=Convert.ToString(item["sha256"]);
            Require(!result.ContainsKey(link),"Duplicate prerequisite part: "+link); result.Add(link,sha);
        }
        foreach(string link in expectedLinks) Require(result.ContainsKey(link),"Prerequisite part missing: "+link);
        return result;
    }

    private static void AddAuthorizedHashes(Dictionary<string,string> target,Dictionary<string,string> source)
    {
        foreach(KeyValuePair<string,string> item in source)
        {
            Require(!target.ContainsKey(item.Key),"Duplicate authorized input: "+item.Key); target.Add(item.Key,item.Value);
        }
    }

    private static Dictionary<string,string> AuthorizedInputHashes(string root,string mode)
    {
        if(mode=="PilotCreate")
        {
            RequireJsonState(root,"07_VERIFICATION/AUTONOMOUS/S05R_J01_PRECHECK/B51R1_S05R_J01_MR1_DRIVER_REFERENCE_HOLD.json",
                "S05R_J01_PREBUILD_HOLD_MR1_ZERO_REFERENCE_INCOMPATIBLE_WITH_OFFSET_DRIVER",false);
            Dictionary<string,object> gate=RequireJsonState(root,
                "07_VERIFICATION/AUTONOMOUS/S05R_PC/B51R1_S05R_PC_MR1_PILOT_COLD_REOPEN_GATE.json",
                "S05R_PC_BASE_AND_LINK1_MR1_COLD_REOPEN_PASS",true);
            return GatePartHashes(gate,new[]{"base_link","link1"});
        }
        if(mode=="PilotVerify")
        {
            Dictionary<string,object> gate=RequireJsonState(root,
                "07_VERIFICATION/AUTONOMOUS/S05R2_P/B51R1_S05R2_P_MR2_PILOT_CREATE_GATE.json",
                "S05R2_P_BASE_AND_LINK1_MR2_CREATED",true);
            return GatePartHashes(gate,new[]{"base_link","link1"});
        }
        if(mode=="BatchCreate")
        {
            RequireJsonState(root,"07_VERIFICATION/AUTONOMOUS/S05R2_J01/B51R1_S05R2_J01_NATIVE_1R_GATE.json",
                "S05R2_J01_NATIVE_1R_PILOT_PASS",true);
            Dictionary<string,object> gate=RequireJsonState(root,
                "07_VERIFICATION/AUTONOMOUS/S05R_B/B51R1_S05R_B_REMAINING_EIGHT_CREATE_GATE.json",
                "S05R_B_REMAINING_EIGHT_MR1_CREATED",true);
            return GatePartHashes(gate,new[]{"link2","link3","link4","link5","link6","gripper_link","gripper_left","gripper_right"});
        }
        if(mode=="AllVerify")
        {
            var result=new Dictionary<string,string>(StringComparer.Ordinal);
            Dictionary<string,object> pilot=RequireJsonState(root,
                "07_VERIFICATION/AUTONOMOUS/S05R2_PC/B51R1_S05R2_PC_MR2_PILOT_COLD_REOPEN_GATE.json",
                "S05R2_PC_BASE_AND_LINK1_MR2_COLD_REOPEN_PASS",true);
            Dictionary<string,object> batch=RequireJsonState(root,
                "07_VERIFICATION/AUTONOMOUS/S05R2_B/B51R1_S05R2_B_REMAINING_EIGHT_CREATE_GATE.json",
                "S05R2_B_REMAINING_EIGHT_MR2_CREATED",true);
            AddAuthorizedHashes(result,GatePartHashes(pilot,new[]{"base_link","link1"}));
            AddAuthorizedHashes(result,GatePartHashes(batch,new[]{"link2","link3","link4","link5","link6","gripper_link","gripper_left","gripper_right"}));
            return result;
        }
        throw new InvalidOperationException("Unknown MR2 mode: "+mode);
    }

    private static Dictionary<string,FileLock> CaptureMr1Locks(string inputDirectory)
    {
        var result=new Dictionary<string,FileLock>(StringComparer.Ordinal);
        foreach(Spec spec in Specs())
        {
            string path=Path.Combine(inputDirectory,spec.InputFile);
            if(!File.Exists(path)) continue;
            result.Add(spec.Link,new FileLock{Link=spec.Link,Path=path,Bytes=new FileInfo(path).Length,Sha256=Sha256(path)});
        }
        return result;
    }

    private static List<Dictionary<string,object>> VerifyMr1Locks(Dictionary<string,FileLock> locks,bool requireUnchanged)
    {
        var evidence=new List<Dictionary<string,object>>();
        foreach(FileLock item in locks.Values)
        {
            bool exists=File.Exists(item.Path); long bytes=exists?new FileInfo(item.Path).Length:-1;
            string sha=exists?Sha256(item.Path):null; bool unchanged=exists&&bytes==item.Bytes&&sha==item.Sha256;
            evidence.Add(new Dictionary<string,object>{{"link",item.Link},{"path",item.Path},{"bytes_before",item.Bytes},
                {"sha256_before",item.Sha256},{"exists_after",exists},{"bytes_after",bytes},{"sha256_after",sha},{"unchanged",unchanged}});
            if(requireUnchanged) Require(unchanged,"Protected MR1 changed: "+item.Link);
        }
        return evidence;
    }

    private static int RunCreate(int expectedProcessId,string inputDirectory,string outputDirectory,
        string receiptPath,string progressPath,int first,int count,string successStatus,string mode,string session)
    {
        var receipt=new Dictionary<string,object>
        {
            {"schema","B51R1_S05R2_DRIVER_READY_CREATE_V2"},{"status","FAIL_CLOSED_NOT_STARTED"},
            {"generated_at_utc",DateTime.UtcNow.ToString("o")},{"expected_process_id",expectedProcessId},
            {"save3_call_count",0},{"save_as_call_count",0},{"publication_method","UNIQUE_STAGING_THEN_NON_OVERWRITE_MOVE"}
        };
        SldWorks app=null; ModelDoc2 model=null; Process process=null;
        var parts=new List<Dictionary<string,object>>(); var stagedParts=new List<StagedPublication>();
        Dictionary<string,FileLock> protectedLocks=null;
        string stagingRoot=null;
        try
        {
            string root=RequireControlledPaths(inputDirectory,outputDirectory,receiptPath,progressPath,session);
            Require(!File.Exists(receiptPath)&&!File.Exists(progressPath),"Append-only MR2 evidence exists");
            Directory.CreateDirectory(outputDirectory); List<Spec> specs=Specs();
            Dictionary<string,string> authorized=AuthorizedInputHashes(root,mode);
            Require(authorized.Count==count,"Authorized input count mismatch for "+mode);
            protectedLocks=CaptureMr1Locks(inputDirectory);
            for(int i=first;i<first+count;i++)
            {
                Spec spec=specs[i]; string input=Path.Combine(inputDirectory,spec.InputFile);
                Require(!File.Exists(Path.Combine(outputDirectory,spec.OutputFile)),"MR2 output exists: "+spec.OutputFile);
                Require(File.Exists(input)&&authorized.ContainsKey(spec.Link)&&Sha256(input)==authorized[spec.Link],
                    "MR1 input is not bound to the prerequisite Gate: "+spec.Link);
            }
            stagingRoot=Path.Combine(outputDirectory,".S05R2_"+session+"_STAGING_"+Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(stagingRoot);
            app=Attach(expectedProcessId); process=Process.GetProcessById(expectedProcessId);
            ProgressCreateNew(progressPath,"MR2_CREATE_START "+DateTime.UtcNow.ToString("o"));
            for(int i=first;i<first+count;i++)
            {
                Spec spec=specs[i]; string input=Path.Combine(inputDirectory,spec.InputFile);
                string output=Path.Combine(outputDirectory,spec.OutputFile);
                string stagedInput=Path.Combine(stagingRoot,"SOURCE_"+spec.InputFile);
                string stagedOutput=Path.Combine(stagingRoot,"OUTPUT_"+spec.OutputFile);
                string before=Sha256(input); File.Copy(input,stagedInput,false);
                Require(Sha256(stagedInput)==before,"Staging copy hash mismatch: "+spec.Link);
                int errors=0,warnings=0; model=app.OpenDoc6(stagedInput,PartType,OpenSilent,"",ref errors,ref warnings) as ModelDoc2;
                Require(model!=null&&errors==0&&warnings==0,"MR1 staging open failed: "+spec.Link);
                Feature added=null; try { if(spec.HasLimitReference) added=AddLimitReference(model,spec); } finally { ReleaseCom(added); }
                receipt["save_as_call_count"]=Convert.ToInt32(receipt["save_as_call_count"])+1;
                ModelDocExtension saveExtension=null; bool saved;
                try { saveExtension=model.Extension; saved=saveExtension.SaveAs(stagedOutput,0,1,null,ref errors,ref warnings); }
                finally { ReleaseCom(saveExtension); }
                Require(saved,"MR2 staged SaveAs failed: "+spec.Link);
                Require(errors==0&&warnings==0,"MR2 staged SaveAs errors/warnings: "+spec.Link+" "+errors+"/"+warnings);
                Dictionary<string,object> item=Inspect(model,spec);
                app.CloseDoc(model.GetTitle()); ReleaseCom(model); model=null;
                Require(app.GetDocumentCount()==0,"Document remained open after MR2 close: "+spec.Link);
                Require(Sha256(input)==before,"MR1 source changed: "+spec.Link);
                Require(File.Exists(stagedOutput),"Staged MR2 output missing: "+spec.Link);
                item["input_path"]=input; item["input_sha256_before_after"]=before;
                item["output_path"]=output; item["output_bytes"]=new FileInfo(stagedOutput).Length;
                item["output_sha256"]=Sha256(stagedOutput);
                stagedParts.Add(new StagedPublication{StagedInput=stagedInput,StagedOutput=stagedOutput,
                    FinalOutput=output,Evidence=item});
                Progress(progressPath,"MR2_STAGING_PASS "+spec.Link+" "+item["output_sha256"]);
            }
            receipt["protected_mr1_hashes_after"]=VerifyMr1Locks(protectedLocks,true);
            app.ExitApp(); ReleaseCom(app); app=null; Require(process.WaitForExit(120000),"Normal exit timed out");
            foreach(StagedPublication staged in stagedParts)
                Require(!File.Exists(staged.FinalOutput),"MR2 output appeared before publication: "+staged.FinalOutput);
            foreach(StagedPublication staged in stagedParts)
            {
                File.Move(staged.StagedOutput,staged.FinalOutput);
                Require(Sha256(staged.FinalOutput)==Convert.ToString(staged.Evidence["output_sha256"]),
                    "Published MR2 hash mismatch: "+staged.FinalOutput);
                File.Delete(staged.StagedInput); parts.Add(staged.Evidence);
                Progress(progressPath,"MR2_CREATE_PASS "+staged.Evidence["link"]+" "+staged.Evidence["output_sha256"]);
            }
            Directory.Delete(stagingRoot,false); stagingRoot=null;
            receipt["parts"]=parts; receipt["created_part_count"]=parts.Count; receipt["normal_document_close"]=true;
            receipt["final_document_count"]=0; receipt["normal_application_exit"]=true;
            receipt["status"]=successStatus; receipt["completed_at_utc"]=DateTime.UtcNow.ToString("o");
            WriteJsonCreateNew(receiptPath,receipt); Progress(progressPath,successStatus); process.Dispose(); return 0;
        }
        catch(Exception ex)
        {
            receipt["parts"]=parts; receipt["created_part_count"]=parts.Count; receipt["status"]="FAIL_CLOSED";
            receipt["exception_type"]=ex.GetType().FullName; receipt["exception"]=ex.ToString();
            if(stagingRoot!=null) receipt["preserved_failure_staging_directory"]=stagingRoot;
            try { if(app!=null&&model!=null) app.CloseDoc(model.GetTitle()); } catch { } ReleaseCom(model); model=null;
            if(protectedLocks!=null) try { receipt["protected_mr1_hashes_after"]=VerifyMr1Locks(protectedLocks,false); } catch { }
            try { if(app!=null&&app.GetDocumentCount()==0) app.ExitApp(); } catch { } ReleaseCom(app);
            if(process!=null) try { process.WaitForExit(120000); process.Dispose(); } catch { }
            try { if(!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath,receipt); } catch { }
            try { if(File.Exists(progressPath)) Progress(progressPath,"FAIL "+ex.Message); } catch { }
            return 1;
        }
    }

    private static int RunVerify(int expectedProcessId,string outputDirectory,string receiptPath,
        string progressPath,int first,int count,string successStatus,string mode,string session)
    {
        var receipt=new Dictionary<string,object>
        {
            {"schema","B51R1_S05R2_DRIVER_READY_COLD_REOPEN_V2"},{"status","FAIL_CLOSED_NOT_STARTED"},
            {"generated_at_utc",DateTime.UtcNow.ToString("o")},{"expected_process_id",expectedProcessId},
            {"save3_call_count",0},{"save_as_call_count",0}
        };
        SldWorks app=null; ModelDoc2 model=null; Process process=null;
        var parts=new List<Dictionary<string,object>>();
        try
        {
            string root=RequireControlledPaths(null,outputDirectory,receiptPath,progressPath,session);
            Require(!File.Exists(receiptPath)&&!File.Exists(progressPath),"Append-only MR2 cold evidence exists");
            Dictionary<string,string> authorized=AuthorizedInputHashes(root,mode);
            Require(authorized.Count==count,"Authorized cold-reopen input count mismatch for "+mode);
            app=Attach(expectedProcessId); process=Process.GetProcessById(expectedProcessId);
            ProgressCreateNew(progressPath,"MR2_COLD_START "+DateTime.UtcNow.ToString("o")); List<Spec> specs=Specs();
            for(int i=first;i<first+count;i++)
            {
                Spec spec=specs[i]; string path=Path.Combine(outputDirectory,spec.OutputFile);
                Require(File.Exists(path)&&authorized.ContainsKey(spec.Link),"MR2 input missing or unauthorized: "+path);
                string before=Sha256(path); Require(before==authorized[spec.Link],"MR2 hash does not match Create Gate: "+spec.Link);
                int errors=0,warnings=0;
                model=app.OpenDoc6(path,PartType,OpenSilent|OpenReadOnly,"",ref errors,ref warnings) as ModelDoc2;
                Require(model!=null&&errors==0&&warnings==0,"MR2 cold reopen failed: "+spec.Link);
                Dictionary<string,object> item=Inspect(model,spec); app.CloseDoc(model.GetTitle()); ReleaseCom(model); model=null;
                Require(app.GetDocumentCount()==0,"Document remained open after cold close: "+spec.Link);
                Require(Sha256(path)==before,"MR2 hash changed on cold reopen: "+spec.Link);
                item["path"]=path; item["bytes"]=new FileInfo(path).Length; item["sha256_before_after"]=before;
                parts.Add(item); Progress(progressPath,"MR2_COLD_PASS "+spec.Link+" "+before);
            }
            app.ExitApp(); ReleaseCom(app); app=null; Require(process.WaitForExit(120000),"Normal exit timed out");
            receipt["parts"]=parts; receipt["verified_part_count"]=parts.Count; receipt["normal_document_close"]=true;
            receipt["final_document_count"]=0; receipt["normal_application_exit"]=true;
            receipt["status"]=successStatus; receipt["completed_at_utc"]=DateTime.UtcNow.ToString("o");
            WriteJsonCreateNew(receiptPath,receipt); Progress(progressPath,successStatus); process.Dispose(); return 0;
        }
        catch(Exception ex)
        {
            receipt["parts"]=parts; receipt["verified_part_count"]=parts.Count; receipt["status"]="FAIL_CLOSED";
            receipt["exception_type"]=ex.GetType().FullName; receipt["exception"]=ex.ToString();
            try { if(app!=null&&model!=null) app.CloseDoc(model.GetTitle()); } catch { } ReleaseCom(model);
            try { if(app!=null&&app.GetDocumentCount()==0) app.ExitApp(); } catch { } ReleaseCom(app);
            if(process!=null) try { process.WaitForExit(120000); process.Dispose(); } catch { }
            try { if(!File.Exists(receiptPath)) WriteJsonCreateNew(receiptPath,receipt); } catch { }
            try { if(File.Exists(progressPath)) Progress(progressPath,"FAIL "+ex.Message); } catch { }
            return 1;
        }
    }

    [STAThread]
    public static int CreatePilot(int expectedProcessId,string inputDirectory,string outputDirectory,string receiptPath,string progressPath)
    {
        return RunCreate(expectedProcessId,inputDirectory,outputDirectory,receiptPath,progressPath,0,2,
            "S05R2_P_BASE_AND_LINK1_MR2_CREATED","PilotCreate","S05R2_P");
    }

    [STAThread]
    public static int VerifyPilot(int expectedProcessId,string outputDirectory,string receiptPath,string progressPath)
    {
        return RunVerify(expectedProcessId,outputDirectory,receiptPath,progressPath,0,2,
            "S05R2_PC_BASE_AND_LINK1_MR2_COLD_REOPEN_PASS","PilotVerify","S05R2_PC");
    }

    [STAThread]
    public static int CreateRemaining(int expectedProcessId,string inputDirectory,string outputDirectory,string receiptPath,string progressPath)
    {
        return RunCreate(expectedProcessId,inputDirectory,outputDirectory,receiptPath,progressPath,2,8,
            "S05R2_B_REMAINING_EIGHT_MR2_CREATED","BatchCreate","S05R2_B");
    }

    [STAThread]
    public static int VerifyAll(int expectedProcessId,string outputDirectory,string receiptPath,string progressPath)
    {
        return RunVerify(expectedProcessId,outputDirectory,receiptPath,progressPath,0,10,
            "S05R2_BC_ALL_TEN_MR2_COLD_REOPEN_PASS","AllVerify","S05R2_BC");
    }
}
